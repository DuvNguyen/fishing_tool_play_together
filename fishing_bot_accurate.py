"""
BOT CÂU CÁ CHÍNH XÁC - LOGIC ĐƠN GIẢN
========================================
- Bấm Space để quăng cần
- Quét dấu chấm than (!) phía trên đầu nhân vật
- Bấm Space để giật cần khi thấy (!)
- KHÔNG click tọa độ linh tinh, chỉ dùng phím Space
========================================
"""

import cv2
import numpy as np
import mss
import sys
# Ensure console can handle UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')
import time
import os
import pydirectinput
import keyboard
import tkinter as tk
import ctypes
from ctypes import wintypes
import random

# Biến toàn cục theo dõi thời gian thao tác (để phớt lờ animation quăng cần thủ công)
last_action_time = 0.0

def on_key_pressed(e):
    global last_action_time
    last_action_time = time.time()

keyboard.on_press_key('space', on_key_pressed)
keyboard.on_press_key('f', on_key_pressed)

NAMETAG_TEMPLATE_FILE = "nametag_template.png"
EXCLAMATION_TEMPLATE_FILE = "exclamation_template.png"
REPAIR_TEMPLATE_FILE = "repair_template.png"
STORE_TEMPLATE_FILE = "store_template.png"

# Tham số nhận diện nametag (tên người chơi)
NAMETAG_THRESHOLD = 0.60
ESTIMATED_TIMEOUT = 2.0  # Giây. Rút ngắn thời gian ước lượng để ép bot quét lại toàn màn hình nhanh hơn nếu bị mất dấu.ve
EXCL_THRESHOLD    = 0.55   # Nhận diện dấu chấm than

# Vùng quét (tính theo bội số chiều cao nametag)
# Dấu chấm than có thể xuất hiện chồng lên hoặc thấp hơn nametag tùy góc cam, 
# nên phải mở rộng khung quét xuống tận dưới chân nhân vật.
SCAN_H_TOP    = 3.0   # Quét tối đa 3.0x chiều cao tên phía trên
SCAN_H_BOTTOM = -1.5  # Mở rộng XUỐNG DƯỚI nametag 1.5x chiều cao (dấu âm nghĩa là đi xuống)
SCAN_W_MARGIN = 0.5   # Mở rộng ngang 0.5x chiều rộng tên

# Thời gian
CAST_WAIT    = 2.5   # Giây chờ sau khi quăng cần (phâo câu ổn định)
LOCK_ON_WAIT = 3.0   # Giây chờ chỉ để lock nametag (không check dấu chấm than)
HARVEST_WAIT = 4.0   # Giây chờ sau khi giật cần (chờ 4s để hiện bảng cá)
STORE_WAIT   = 2.0   # Giây chờ sau khi bấm X để cất cá
TIMEOUT      = 45.0  # Timeout chờ cá cắn (giây)

# Dấu chấm than có 2 màu: HỒNG TÍM và VÀNG.
# Chúng ta sử dụng logic so sánh tương đối để loại bỏ hoàn toàn bọt nước trắng/cyan hoặc bóng xám.
# Dấu chấm than kích thước rất lớn (khoảng 2000+ pixel), trong khi phao câu (bobber) chỉ có ~37 pixel.
EXCL_PIXEL_COUNT_THRESHOLD = 100   # Mức lọc hoàn hảo để phớt lờ hoàn toàn cái phao câu lướt qua
EXCL_CONSECUTIVE_REQUIRED = 2   # Cần 2 khung hình liên tiếp để lọc nhiễu 1 frame


# Vùng an toàn khi tìm kiếm nametag toàn màn hình
# (Loại bỏ: 5% trên = icon UI, 20% dưới = thanh chat + nút UI)
SEARCH_SKIP_TOP    = 0.05  # Bỏ 5% trên
SEARCH_SKIP_BOTTOM = 0.20  # Bỏ 20% dưới

# Thời gian tối đa dùng estimated position mà không có real detection
# ESTIMATED_TIMEOUT = 6.0  # Đã chuyển lên trên

# Thời gian chờ trước khi bắt đầu nhận diện dấu chấm than
PRE_EXCL_WAIT = 0.0   # Giây chờ sau khi đã lock nametag thực, trước khi bắt đầu detect (!)

pydirectinput.PAUSE = 0

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

GetWindowRect = ctypes.windll.user32.GetWindowRect
GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
GetWindowRect.restype = ctypes.windll.user32.GetWindowRect.restype

class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "black")
        try:
            self.root.wm_attributes("-disabled", True)
        except:
            pass
        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+0+0")
        self.canvas = tk.Canvas(self.root, width=w, height=h, bg="black", highlightthickness=0)
        self.canvas.pack()

    def draw(self, nametag_box, scan_box, hooked_box=None, score=0.0, name_score=0.0, estimated=False):
        self.canvas.delete("all")
        if nametag_box:
            x, y, w, h = nametag_box
            color = "#FF9900" if estimated else "#00FF00"
            label = f"Target ({'Est' if estimated else 'Lock'}: {name_score:.2f})"
            self.canvas.create_rectangle(x, y, x+w, y+h, outline=color, width=2)
            self.canvas.create_text(x, y-10, text=label, fill=color, anchor="w")
        if scan_box:
            x, y, w, h = scan_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#0099FF", width=2)
            self.canvas.create_text(x, y-10, text=f"Change: {score:.2f}", fill="#0099FF", anchor="w")
        if hooked_box:
            x, y, w, h = hooked_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#FF0000", width=3)
            self.canvas.create_text(x, y-12, text=f"HOOKED! {score:.2f}", fill="#FF0000", anchor="w")

    def update(self):
        self.root.update()

def find_multiscale(img_gray, tmpl_gray, scales):
    best_val, best_loc, best_scale = -1.0, None, 1.0
    th, tw = tmpl_gray.shape
    for s in scales:
        rw, rh = int(tw * s), int(th * s)
        if img_gray.shape[0] < rh or img_gray.shape[1] < rw:
            continue
        tmpl_r = cv2.resize(tmpl_gray, (rw, rh), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(img_gray, tmpl_r, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        if val > best_val:
            best_val, best_loc, best_scale = val, loc, s
    return best_val, best_loc, best_scale

def find_nametag_center_bias(img_gray, tmpl_gray, scales):
    """
    Tìm nametag với bô sung penalty khoảng cách tới tâm.
    Giúp loại bỏ false positive ở góc màn hình khi template match bị sai.
    """
    h_img, w_img = img_gray.shape
    cx, cy = w_img / 2.0, h_img / 2.0  # Tâm vùng chụp
    # Khoảng cách tối đa có thể (góc màn hình)
    max_dist = (cx**2 + cy**2) ** 0.5
    PENALTY_WEIGHT = 0.15  # Giảm tối đa 0.15 điểm score ở góc xa nhất

    best_score, best_loc, best_scale = -1.0, None, 1.0
    th, tw = tmpl_gray.shape
    for s in scales:
        rw, rh = int(tw * s), int(th * s)
        if img_gray.shape[0] < rh or img_gray.shape[1] < rw:
            continue
        tmpl_r = cv2.resize(tmpl_gray, (rw, rh), interpolation=cv2.INTER_AREA)
        if cv2.countNonZero(tmpl_r) < 5:
            continue
        res = cv2.matchTemplate(img_gray, tmpl_r, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        # Tính khoảng cách từ vị trí khớp tới tâm ảnh
        match_cx = loc[0] + rw / 2.0
        match_cy = loc[1] + rh / 2.0
        dist = ((match_cx - cx)**2 + (match_cy - cy)**2) ** 0.5
        # Áp dụng penalty theo khoảng cách
        penalty = PENALTY_WEIGHT * (dist / max_dist)
        adjusted = val - penalty
        if adjusted > best_score:
            best_score, best_loc, best_scale = adjusted, loc, s
    return best_score, best_loc, best_scale

is_paused = False

def check_pause(overlay):
    global is_paused
    if keyboard.is_pressed('p'):
        is_paused = not is_paused
        if is_paused:
            print("\n[!] Đã TẠM DỪNG bot. Bấm P để tiếp tục...")
        else:
            print("\n[+] Đã TIẾP TỤC bot...")
        time.sleep(0.3)
        
    pause_dur = 0.0
    if is_paused:
        t0 = time.time()
        while is_paused:
            overlay.update()
            if keyboard.is_pressed('q') or keyboard.is_pressed('r') or keyboard.is_pressed('e'):
                break
            if keyboard.is_pressed('p'):
                is_paused = False
                print("\n[+] Đã TIẾP TỤC bot...")
                time.sleep(0.3)
            time.sleep(0.02)
        pause_dur = time.time() - t0
    return pause_dur

def sleep_ui(seconds, overlay):
    end = time.time() + seconds
    while time.time() < end:
        overlay.update()
        if keyboard.is_pressed('q'): return 'q'
        if keyboard.is_pressed('r'): return 'r'
        if keyboard.is_pressed('e'): return 'e'
        end += check_pause(overlay)
        time.sleep(0.02)
    return None
def scan_template_routine(win_title, output_file, success_msg):
    import mss
    import cv2
    import numpy as np
    import time
    from tkinter import messagebox
    
    time.sleep(0.5)
    sct = mss.mss()
    monitor = sct.monitors[1]
    sct_img = sct.grab(monitor)
    img = np.array(sct_img)
    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    cv2.namedWindow(win_title, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win_title, cv2.WND_PROP_TOPMOST, 1)
    
    roi = cv2.selectROI(win_title, img_bgr, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(win_title)
    for _ in range(10):
        cv2.waitKey(1)
    
    if roi[2] > 0 and roi[3] > 0:
        rx, ry, rw, rh = roi
        tmpl = img_bgr[ry:ry+rh, rx:rx+rw]
        cv2.imwrite(output_file, tmpl)
        messagebox.showinfo("Thanh cong", success_msg)

def show_control_panel(parent=None):
    if parent:
        panel = tk.Toplevel(parent)
    else:
        panel = tk.Tk()
    panel.title("Fishing Bot - Bang Dieu Khien")
    panel.geometry("400x350")
    panel.attributes("-topmost", True)
    
    w, h = 400, 350
    sw = panel.winfo_screenwidth()
    sh = panel.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    panel.geometry(f"{w}x{h}+{x}+{y}")

    def on_scan_name():
        panel.withdraw()
        scan_template_routine("CHON NAMETAG NHAN VAT", NAMETAG_TEMPLATE_FILE, "Da luu Nametag moi thanh cong!")
        panel.deiconify()

    def on_scan_repair():
        panel.withdraw()
        scan_template_routine("CHON CHU 'THONG TIN SUA CHUA'", REPAIR_TEMPLATE_FILE, "Da luu mau Sửa Cần thanh cong!")
        panel.deiconify()

    def on_scan_store():
        panel.withdraw()
        scan_template_routine("CHON CHU 'BAO QUAN'", STORE_TEMPLATE_FILE, "Da luu mau Bảo Quản thanh cong!")
        panel.deiconify()

    def on_start():
        global HARVEST_WAIT
        import os
        from tkinter import messagebox
        try:
            HARVEST_WAIT = float(harvest_wait_var.get())
        except ValueError:
            pass
        if not os.path.exists(NAMETAG_TEMPLATE_FILE):
            messagebox.showerror("Loi", "Chua co file nametag_template.png!\nVui long Quet Nametag Moi truoc.")
            return
        if not os.path.exists(EXCLAMATION_TEMPLATE_FILE):
            messagebox.showerror("Loi", "Thieu file exclamation_template.png!\nVui long copy file nay vao cung thu muc voi file exe.")
            return
        panel.destroy()

    tk.Label(panel, text="FISHING BOT - PLAY TOGETHER", font=("Arial", 14, "bold")).pack(pady=10)
    
    frame_wait = tk.Frame(panel)
    frame_wait.pack(pady=5)
    tk.Label(frame_wait, text="Thời gian kéo cá mặc định (giây):", font=("Arial", 10)).pack(side=tk.LEFT)
    harvest_wait_var = tk.StringVar(value=str(HARVEST_WAIT))
    tk.Entry(frame_wait, textvariable=harvest_wait_var, font=("Arial", 10), width=5).pack(side=tk.LEFT, padx=5)

    tk.Button(panel, text="1. Quet Nametag Moi", command=on_scan_name, font=("Arial", 11), bg="#FF9900", fg="white").pack(pady=5, fill='x', padx=20)
    tk.Button(panel, text="2. Quet Giao Dien Sua Can", command=on_scan_repair, font=("Arial", 11), bg="#3399FF", fg="white").pack(pady=5, fill='x', padx=20)
    tk.Button(panel, text="3. Quet Chu 'Bao Quan' (Tuy Chon)", command=on_scan_store, font=("Arial", 11), bg="#9933FF", fg="white").pack(pady=5, fill='x', padx=20)
    tk.Button(panel, text="4. Bat Dau Chay Bot", command=on_start, font=("Arial", 12), bg="#00CC00", fg="white").pack(pady=10, fill='x', padx=20)
    
    if parent:
        panel.wait_window()
    else:
        panel.mainloop()

def main():
    print("==================================================")
    print("  BOT CAU CA (SPACE ONLY - KHONG CLICK LINH TINH)")
    print("==================================================")
    print("Logic don gian:")
    print("  Space -> Quang ca")
    print("  Thay (!) -> Space -> Git can")
    print("  Space -> Cat ca -> lap lai")
    print("--------------------------------------------------")
    print("Phím: R=Bắt đầu/Restart, P=Tạm dừng, Q=Thoát, E=Cài đặt")
    print("==================================================")

    show_control_panel()

    # Kiểm tra file template
    if not os.path.exists(NAMETAG_TEMPLATE_FILE):
        print(f"[Loi] Thieu file '{NAMETAG_TEMPLATE_FILE}'. Chay calibrate.py bam 'N'.")
        return
    if not os.path.exists(EXCLAMATION_TEMPLATE_FILE):
        print(f"[Loi] Thieu file '{EXCLAMATION_TEMPLATE_FILE}'. Chay calibrate.py bam 'T'.")
        return

    # Load templates
    # Load template nametag và tạo mask xanh lá thay vì dùng ảnh xám
    nametag_tmpl_color = cv2.imread(NAMETAG_TEMPLATE_FILE)
    if nametag_tmpl_color is None:
        import tkinter.messagebox
        tkinter.messagebox.showerror("Loi", f"Khong the doc file {NAMETAG_TEMPLATE_FILE}!")
        return
    nametag_tmpl_green = cv2.inRange(nametag_tmpl_color, np.array([0, 150, 0]), np.array([100, 255, 100]))
    nt_h, nt_w = nametag_tmpl_green.shape

    sct = mss.mss()
    sw = sct.monitors[1]["width"]
    sh = sct.monitors[1]["height"]

    overlay = Overlay()
    print("[+] Bot chạy! Nhấn Q để dừng, R để khởi động lại.")
    sleep_ui(0.5, overlay)

    # --- Biến tracking ---
    last_box      = None   # (x, y, w, h) tuyệt đối - nametag
    known_rx      = None   # Relative x trong cửa sổ game
    known_ry      = None
    known_scale   = 1.0
    tracking_pad  = 200    # Padding vùng chụp khi đã lock
    last_real_detect_time = 0.0  # Lần cuối detect được tên thật

    # Tìm cửa sổ game để lấy HWND (dùng cho lock offset khi tên bị ẩn)
    hwnd = ctypes.windll.user32.GetForegroundWindow()

    NAMETAG_SCALES = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
    EXCL_SCALES    = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]

    current_turn = 0
    target_turns = random.randint(4, 5)

    try:
        while True:
            if keyboard.is_pressed('q'): break
            if keyboard.is_pressed('r'):
                print("[+] Đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue
            if keyboard.is_pressed('e'):
                print("\n[+] Đang mở lại bảng cài đặt...")
                show_control_panel(overlay.root)
                print("[+] Đã đóng cài đặt, đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue

            # ========== STEP 1: QUĂNG CẦN ==========
            print("[+] Quăng câu (F)...")
            overlay.draw(None, None)
            overlay.update()
            pydirectinput.press('f')

            # Kiểm tra xem có hiện bảng sửa cần không (đợi xíu cho animation popup)
            res = sleep_ui(0.8, overlay)
            
            repair_detected = False
            if os.path.exists(REPAIR_TEMPLATE_FILE):
                repair_tmpl = cv2.imread(REPAIR_TEMPLATE_FILE, cv2.IMREAD_GRAYSCALE)
                if repair_tmpl is not None:
                    sct_img = sct.grab(sct.monitors[1])
                    img_gray = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2GRAY)
                    res_match = cv2.matchTemplate(img_gray, repair_tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res_match)
                    if max_val > 0.8:
                        repair_detected = True

            if repair_detected:
                print("\n[!] Cần bị hỏng! Đang tự động sửa (bấm O)...")
                pydirectinput.press('o')
                sleep_ui(1.0, overlay)
                print("[+] Đã sửa xong, quăng cần lại!")
                continue

            # Nếu không phải sửa cần, thì chờ nốt phần thời gian còn lại của CAST_WAIT
            if res not in ['q', 'r']:
                res = sleep_ui(CAST_WAIT - 0.8, overlay)

            if res == 'q' or keyboard.is_pressed('q'): break
            if res == 'e' or keyboard.is_pressed('e'):
                print("\n[+] Đang mở lại bảng cài đặt...")
                show_control_panel(overlay.root)
                print("[+] Đã đóng cài đặt, đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue
            if res == 'r' or keyboard.is_pressed('r'):
                print("[+] Đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue

            # ========== STEP 1.5: LOCK-ON NAMETAG (không check dấu chấm than) ==========
            print(f"[~] Lock-on nametag ({LOCK_ON_WAIT}s)...")
            lock_deadline = time.time() + LOCK_ON_WAIT
            restart_flag = False
            while time.time() < lock_deadline:
                overlay.update()
                if keyboard.is_pressed('q'):
                    break
                if keyboard.is_pressed('r'):
                    restart_flag = 'r'
                    break
                if keyboard.is_pressed('e'):
                    restart_flag = 'e'
                    break
                lock_deadline += check_pause(overlay)

                rect = wintypes.RECT()
                GetWindowRect(hwnd, ctypes.byref(rect))
                wx, wy = rect.left, rect.top

                safe_top = int(sh * SEARCH_SKIP_TOP)
                safe_bottom = int(sh * (1 - SEARCH_SKIP_BOTTOM))
                mon_lock = {"top": safe_top, "left": 0, "width": sw, "height": safe_bottom - safe_top}
                sct_img = sct.grab(mon_lock)
                # Tìm nametag bằng mask xanh lá để chống nhiễu phông nền
                frame_color = np.array(sct_img)[:, :, :3]
                frame_green = cv2.inRange(frame_color, np.array([0, 150, 0]), np.array([100, 255, 100]))
                
                ns, nloc, nscale = find_nametag_center_bias(frame_green, nametag_tmpl_green, NAMETAG_SCALES)
                if ns >= NAMETAG_THRESHOLD:
                    nx_rel, ny_rel = nloc
                    nw = int(nt_w * nscale)
                    nh = int(nt_h * nscale)
                    
                    # Trích xuất vùng màu và kiểm tra chữ xanh lá (Green text)
                    nt_roi_color = np.array(sct_img)[ny_rel:ny_rel+nh, nx_rel:nx_rel+nw, :3]
                    # Chữ xanh lá có mã màu xấp xỉ BGR = (0, 255, 0)
                    green_mask = cv2.inRange(nt_roi_color, np.array([0, 150, 0]), np.array([100, 255, 100]))
                    
                    if cv2.countNonZero(green_mask) > 50:
                        nx_abs = nx_rel + 0
                        ny_abs = ny_rel + safe_top
                        last_box  = (nx_abs, ny_abs, nw, nh)
                        known_rx  = nx_abs - wx
                        known_ry  = ny_abs - wy
                        known_scale = nscale
                        last_real_detect_time = time.time()
                        overlay.draw(last_box, None, name_score=ns)
                        print(f"  [Lock] Name: {ns:.2f} ✓           ", end="\r")
                    else:
                        ns = 0.0 # Bỏ qua vì không phải nametag màu xanh lá
                        overlay.draw(None, None)
                        print(f"  [Lock] Đang tìm nametag (bỏ qua tên màu khác)...", end="\r")
                else:
                    overlay.draw(None, None)
                    print(f"  [Lock] Đang tìm nametag ({ns:.2f})...", end="\r")
                time.sleep(0.05)

            print()  # xuống dòng sau lock-on
            if keyboard.is_pressed('q'): break
            if restart_flag == 'e' or keyboard.is_pressed('e'):
                print("\n[+] Đang mở lại bảng cài đặt...")
                show_control_panel(overlay.root)
                print("[+] Đã đóng cài đặt, đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue
            if restart_flag == 'r' or keyboard.is_pressed('r'):
                print("[+] Đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue

            # ========== STEP 2: CHỜ CÁ CẮN (định vị nametag) ==========
            print("[*] Đang chờ cá cắn (định vị nametag)...")
            fish_bited = False
            t_start = time.time()
            # biến quản lý trạng thái change detection
            fixed_scan_box = None # lưu vùng quét cố định trên màn hình
            fixed_scan_box_time = 0 # thời điểm khung quét xuất hiện
            baseline_excl_pixels = -1 # Lưu số lượng pixel hồng/vàng tĩnh (ví dụ: cần câu)
            excl_consecutive = 0

            while time.time() - t_start < TIMEOUT:
                overlay.update()
                if keyboard.is_pressed('q'):
                    break
                if keyboard.is_pressed('r'):
                    restart_flag = 'r'
                    break
                if keyboard.is_pressed('e'):
                    restart_flag = 'e'
                    break
                
                pdur = check_pause(overlay)
                t_start += pdur
                if fixed_scan_box_time > 0:
                    fixed_scan_box_time += pdur

                # Lấy vị trí cửa sổ game (để tính offset khi tên bị ẩn)
                rect = wintypes.RECT()
                GetWindowRect(hwnd, ctypes.byref(rect))
                wx, wy = rect.left, rect.top

                # Xác định vùng chụp màn hình
                if last_box is None:
                    # Toàn màn hình nhưng bỏ qua vùng chat/UI (trên và dưới)
                    safe_top = int(sh * SEARCH_SKIP_TOP)
                    safe_bottom = int(sh * (1 - SEARCH_SKIP_BOTTOM))
                    mon = {"top": safe_top, "left": 0, "width": sw, "height": safe_bottom - safe_top}
                    ox, oy = 0, safe_top
                else:
                    lx, ly, lw, lh = last_box
                    mon = {
                        "top":    max(0, ly - tracking_pad),
                        "left":   max(0, lx - tracking_pad),
                        "width":  min(sw - max(0, lx - tracking_pad), lw + 2 * tracking_pad),
                        "height": min(sh - max(0, ly - tracking_pad), lh + 2 * tracking_pad)
                    }
                    ox, oy = mon["left"], mon["top"]

                sct_img = sct.grab(mon)
                frame_gray = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2GRAY)

                estimated = False
                nametag_box = last_box

                if fixed_scan_box is None:
                    frame_color = np.array(sct_img)[:, :, :3]
                    frame_green = cv2.inRange(frame_color, np.array([0, 150, 0]), np.array([100, 255, 100]))
                    ns, nloc, nscale = find_nametag_center_bias(frame_green, nametag_tmpl_green, NAMETAG_SCALES)

                    if ns >= NAMETAG_THRESHOLD:
                        # Tìm thấy tên -> cập nhật vị trí + lưu thời điểm
                        nx_rel, ny_rel = nloc
                        nw = int(nt_w * nscale)
                        nh = int(nt_h * nscale)
                        
                        # Kiểm tra chữ màu xanh lá (Green text)
                        nt_roi_color = np.array(sct_img)[ny_rel:ny_rel+nh, nx_rel:nx_rel+nw, :3]
                        green_mask = cv2.inRange(nt_roi_color, np.array([0, 150, 0]), np.array([100, 255, 100]))
                        
                        green_pixels = cv2.countNonZero(green_mask)
                        # Text nametag mỏng nên số lượng pixel xanh dao động từ 50 đến 3000.
                        # Nút bấm UI màu xanh (ví dụ: Bảo quản) là một mảng xanh đặc lớn, sẽ có hàng ngàn pixel (>5000).
                        # Việc giới hạn < 4000 giúp loại bỏ hoàn toàn việc bắt nhầm nút bấm UI!
                        if 50 < green_pixels < 4000:
                            nx_abs = nx_rel + ox
                            ny_abs = ny_rel + oy
                            last_box    = (nx_abs, ny_abs, nw, nh)
                            known_rx    = nx_abs - wx
                            known_ry    = ny_abs - wy
                            known_scale = nscale
                            nametag_box = last_box
                            last_real_detect_time = time.time()  # Cập nhật lần detect thật
                            excl_consecutive = 0
                        else:
                            ns = 0.0 # Ép rớt xuống block estimated
                            
                    if ns < NAMETAG_THRESHOLD and known_rx is not None:
                        # Tên bị ẩn -> kiểm tra có bị estimated quá lâu không
                        if time.time() - last_real_detect_time > ESTIMATED_TIMEOUT:
                            # Đã dùng estimated quá lâu -> có thể sai -> reset toàn bộ
                            print(f"\n[!] Estimated quá {ESTIMATED_TIMEOUT}s không detect được tên thật -> Reset scan.")
                            known_rx = None
                            known_ry = None
                            last_box = None
                            prev_roi = None
                        else:
                            # Ước lượng từ offset đã lưu
                            nx_abs = wx + known_rx
                            ny_abs = wy + known_ry
                            nscale = known_scale
                            nw = int(nt_w * nscale)
                            nh = int(nt_h * nscale)
                            nametag_box = (nx_abs, ny_abs, nw, nh)
                            last_box    = nametag_box
                            estimated   = True
                            nx_rel = nx_abs - ox
                            ny_rel = ny_abs - oy
                else:
                    # BỎ QUA việc tìm nametag nếu đã khóa được vùng quét dấu chấm than!
                    # Điều này giúp vòng lặp chạy với tốc độ cực cao (bỏ qua hàm search nặng) -> phản xạ tức thời!
                    ns = 1.0 
                    estimated = True

                if nametag_box and fixed_scan_box is None:
                    nx_abs, ny_abs, nw, nh = nametag_box
                    # Tính vùng quét dấu chấm than 1 lần duy nhất và cố định nó
                    sy1 = max(0, (ny_abs - oy) - int(nh * SCAN_H_TOP))
                    sy2 = max(0, (ny_abs - oy) - int(nh * SCAN_H_BOTTOM))
                    sx1 = max(0, (nx_abs - ox) - int(nw * SCAN_W_MARGIN))
                    sx2 = min(mon["width"], (nx_abs - ox) + nw + int(nw * SCAN_W_MARGIN))

                    if sy2 > sy1 and sx2 > sx1:
                        fixed_scan_box = (sx1 + ox, sy1 + oy, sx2 - sx1, sy2 - sy1)
                        fixed_scan_box_time = time.time() # Lưu thời điểm khung vừa xuất hiện
                        print(f"\n[*] Đã định hình vùng quét chấm than cố định.")
                
                if fixed_scan_box is not None:
                    fsx_abs, fsy_abs, fsw, fsh = fixed_scan_box
                    # Chuyển đổi tọa độ tuyệt đối sang tọa độ trong frame hiện tại
                    fsx_rel = fsx_abs - ox
                    fsy_rel = fsy_abs - oy
                    
                    if fsy_rel >= 0 and fsy_rel + fsh <= mon["height"] and fsx_rel >= 0 and fsx_rel + fsw <= mon["width"]:
                        # Trích xuất ROI màu BGR
                        roi_color = np.array(sct_img)[fsy_rel:fsy_rel+fsh, fsx_rel:fsx_rel+fsw, :3]
                        
                        # 1. Quét màu hồng tím đặc trưng của dấu chấm than bằng logic tương đối
                        b = roi_color[:, :, 0].astype(np.int16)
                        g = roi_color[:, :, 1].astype(np.int16)
                        r = roi_color[:, :, 2].astype(np.int16)
                        
                        # 1. Quét màu hồng (Pink) - Đã mở rộng dải màu từ nhạt đến đậm
                        # Màu hồng: Red là màu chủ đạo (hoặc tương đương Blue), cao hơn Green.
                        mask_p_r = r > 100
                        mask_p_rg = (r - g) > 8
                        mask_p_bg = (b - g) > -25
                        pink_mask = (mask_p_r & mask_p_rg & mask_p_bg).astype(np.uint8)
                        
                        # 2. Quét màu VÀNG (Yellow) từ nhạt đến đậm
                        mask_y_r = r > 120
                        mask_y_g = g > 120
                        mask_y_rb = (r - b) > 15
                        mask_y_gb = (g - b) > 15
                        yellow_mask = (mask_y_r & mask_y_g & mask_y_rb & mask_y_gb).astype(np.uint8)

                        # Loại bỏ các màu trắng/cam/xanh lá vì dễ gây nhiễu với bọt nước và nền trời/nước
                        
                        # Tổng hợp các loại chấm than (Chỉ dùng Hồng tím và Vàng để chống nhiễu nước)
                        final_mask = pink_mask | yellow_mask
                        excl_pixels = cv2.countNonZero(final_mask)
                        
                        # Cập nhật baseline (mức nhiễu nền tĩnh) bằng giá trị lớn nhất trong 1.5s đầu
                        if time.time() - fixed_scan_box_time <= 1.5:
                            if baseline_excl_pixels == -1 or excl_pixels > baseline_excl_pixels:
                                baseline_excl_pixels = excl_pixels
                                
                        # Chỉ bắt đầu ghi nhận thay đổi nếu khung đã xuất hiện được 1.5 giây
                        # VÀ PHẢI CÁCH LẦN BẤM SPACE/F GẦN NHẤT ÍT NHẤT 2.5 GIÂY!
                        elif time.time() - fixed_scan_box_time > 1.5 and time.time() - last_action_time > 2.5:
                            if baseline_excl_pixels == -1:
                                baseline_excl_pixels = excl_pixels
                                print(f"[*] Đã lấy mẫu nền màu tĩnh (hồng/vàng): {baseline_excl_pixels} pixels")
                            
                            # Tính lượng pixel TĂNG ĐỘT BIẾN so với nền tĩnh
                            diff_pixels = excl_pixels - baseline_excl_pixels
                            
                            if diff_pixels >= EXCL_PIXEL_COUNT_THRESHOLD:
                                excl_consecutive += 1
                            else:
                                excl_consecutive = 0
                                
                            if diff_pixels > 5:
                                print(f"[*] Diff Pixels: {diff_pixels} (consecutive: {excl_consecutive})")
                        else:
                            excl_consecutive = 0
                            
                        if excl_consecutive >= EXCL_CONSECUTIVE_REQUIRED:
                            ex_abs = fsx_abs + int(fsw / 2)
                            ey_abs = fsy_abs + int(fsh / 2)
                            hooked_box = (ex_abs, ey_abs, 1, 1)
                            # Hiển thị số lượng pixel thực sự tăng vọt
                            overlay.draw(nametag_box, fixed_scan_box, hooked_box, diff_pixels, ns, estimated)
                            overlay.update()
                            print(f"\n[!!!] CÁ CẮN! Diff Pixels: {diff_pixels} (x{excl_consecutive}) -> SPACE!")
                            pydirectinput.press('space')
                            fish_bited = True
                            break

                    # Hiển thị mức tăng đột biến lên màn hình thay vì tổng số pixel
                    display_val = 0
                    if 'diff_pixels' in locals() and time.time() - fixed_scan_box_time > 1.5 and time.time() - last_action_time > 2.5:
                        display_val = diff_pixels
                    elif 'excl_pixels' in locals():
                        display_val = excl_pixels
                        
                    overlay.draw(nametag_box, fixed_scan_box, None, display_val, ns, estimated)

                time.sleep(0.02)

            if keyboard.is_pressed('q'): break
            if restart_flag == 'e' or keyboard.is_pressed('e'):
                print("\n[+] Đang mở lại bảng cài đặt...")
                show_control_panel(overlay.root)
                print("[+] Đã đóng cài đặt, đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue
            if restart_flag == 'r' or keyboard.is_pressed('r'):
                print("[+] Đang khởi động lại...")
                last_box, known_rx, known_ry = None, None, None
                sleep_ui(0.5, overlay)
                continue

            if fish_bited:
                # ========== STEP 3: CHỜ ANIMATION KÉO CÁ ==========
                print(f"[+] Đang kéo cá... (chờ {HARVEST_WAIT}s)")
                
                store_tmpl = None
                if os.path.exists(STORE_TEMPLATE_FILE):
                    store_tmpl = cv2.imread(STORE_TEMPLATE_FILE, cv2.IMREAD_GRAYSCALE)
                
                res = None
                if store_tmpl is not None:
                    print("[*] Đang tìm chữ 'Bảo quản' (tự động nhận diện)...")
                    # Nếu có nhận diện, cho phép đợi tối đa 15s (đề phòng cá to)
                    wait_end = time.time() + max(15.0, HARVEST_WAIT)
                    found_store = False
                    while time.time() < wait_end:
                        overlay.update()
                        if keyboard.is_pressed('q'):
                            res = 'q'
                            break
                        if keyboard.is_pressed('r'):
                            res = 'r'
                            break
                        if keyboard.is_pressed('e'):
                            res = 'e'
                            break
                        
                        sct_img = sct.grab(sct.monitors[1])
                        img_gray = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2GRAY)
                        res_match = cv2.matchTemplate(img_gray, store_tmpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res_match)
                        if max_val > 0.8:
                            found_store = True
                            print("[+] Đã thấy nút Bảo quản!")
                            time.sleep(0.5) # Chờ UI hiện ra hoàn toàn
                            break
                        
                        time.sleep(0.1)
                        wait_end += check_pause(overlay)
                        
                else:
                    res = sleep_ui(HARVEST_WAIT, overlay)

                if res == 'e' or keyboard.is_pressed('e'):
                    print("\n[+] Đang mở lại bảng cài đặt...")
                    show_control_panel(overlay.root)
                    print("[+] Đã đóng cài đặt, đang khởi động lại...")
                    last_box, known_rx, known_ry = None, None, None
                    sleep_ui(0.5, overlay)
                    continue

                if res == 'r' or keyboard.is_pressed('r'):
                    print("[+] Đang khởi động lại...")
                    last_box, known_rx, known_ry = None, None, None
                    sleep_ui(0.5, overlay)
                    continue

                if res == 'q' or keyboard.is_pressed('q'):
                    break

                # ========== STEP 4: BẢO QUẢN CÁ (X) rồi sẵn sàng câu lại ==========
                print("[+] Bảo quản cá (X)...")
                pydirectinput.press('x')
                res = sleep_ui(STORE_WAIT, overlay)
                if res == 'e' or keyboard.is_pressed('e'):
                    print("\n[+] Đang mở lại bảng cài đặt...")
                    show_control_panel(overlay.root)
                    print("[+] Đã đóng cài đặt, đang khởi động lại...")
                    last_box, known_rx, known_ry = None, None, None
                    sleep_ui(0.5, overlay)
                    continue
                if res == 'r' or keyboard.is_pressed('r'):
                    print("[+] Đang khởi động lại...")
                    last_box, known_rx, known_ry = None, None, None
                    current_turn = 0
                    target_turns = random.randint(4, 5)
                    sleep_ui(0.5, overlay)
                    continue

                current_turn += 1
                if current_turn >= target_turns:
                    print(f"[+] Đã đạt {current_turn} lượt câu. Tự động reset vòng câu (bấm R)...")
                    pydirectinput.press('r')
                    sleep_ui(1.0, overlay)
                    current_turn = 0
                    target_turns = random.randint(4, 5)
            else:
                print("[-] Hết giờ, thu cần lại (F)...")
                pydirectinput.press('f')
                res = sleep_ui(1.5, overlay)
                if res == 'e' or keyboard.is_pressed('e'):
                    print("\n[+] Đang mở lại bảng cài đặt...")
                    show_control_panel(overlay.root)
                    print("[+] Đã đóng cài đặt, đang khởi động lại...")
                    last_box, known_rx, known_ry = None, None, None
                    sleep_ui(0.5, overlay)
                    continue
                if res == 'r' or keyboard.is_pressed('r'):
                    print("[+] Đang khởi động lại...")
                    last_box, known_rx, known_ry = None, None, None
                    sleep_ui(0.5, overlay)
                    continue
                
            # XÓA BỘ NHỚ TRACKING ĐỂ QUÉT LẠI TỪ ĐẦU!
            # Nếu không xóa, bot sẽ dùng lại tọa độ cũ, dẫn đến việc nhận diện sai lệch
            # nếu nhân vật bị dịch chuyển sau khi bắt được cá.
            print("[+] Đặt lại hệ thống tracking cho lượt câu mới.")
            last_box = None
            known_rx = None
            known_ry = None
            prev_roi = None

    except Exception as e:
        print(f"[Loi] {e}")
    finally:
        overlay.draw(None, None)
        print("[!] Bot dừng.")

if __name__ == "__main__":
    main()
