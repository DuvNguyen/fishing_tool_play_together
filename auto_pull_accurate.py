import cv2
import numpy as np
import mss
import time
import os
import pydirectinput
import keyboard
import tkinter as tk

NAMETAG_TEMPLATE_FILE = "nametag_template.png"
EXCLAMATION_TEMPLATE_FILE = "exclamation_template.png"
THRESHOLD = 0.70  # Độ khớp tối thiểu để xác nhận là dấu chấm than (0.0 đến 1.0)

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
        
    def draw_boxes(self, nametag_box, scan_box, matched_box=None, score=0.0):
        self.canvas.delete("all")
        if nametag_box:
            x, y, w, h = nametag_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#00FF00", width=2)
            self.canvas.create_text(x, y-10, text="Name Detected", fill="#00FF00", anchor="w")
        if scan_box:
            x, y, w, h = scan_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#0000FF", width=2)
        if matched_box:
            mx, my, mw, mh = matched_box
            # Khung màu ĐỎ hiển thị khi phát hiện chính xác dấu chấm than
            self.canvas.create_rectangle(mx, my, mx+mw, my+mh, outline="#FF0000", width=3)
            self.canvas.create_text(mx, my-12, text=f"HOOKED! ({score:.2f})", fill="#FF0000", anchor="w")
            
    def update_window(self):
        self.root.update()

def main():
    print("==================================================")
    print("      AUTO-PULL (CHINH XAC CHONG BAO GIA CONG)")
    print("==================================================")
    print("Cơ chế hoạt động:")
    print(" 1. Định vị tên nhân vật bằng màu xanh lá (chống zoom camera).")
    print(" 2. Chỉ quét tìm hình ảnh dấu chấm than (!) bên trong vùng màu xanh dương.")
    print(" 3. Khớp chính xác hình dáng (!) mới thực hiện giật cần.")
    print("==================================================")

    if not os.path.exists(EXCLAMATION_TEMPLATE_FILE):
        print(f"[!] LOI: Thieu file '{EXCLAMATION_TEMPLATE_FILE}'!")
        return

    # Load ảnh mẫu dấu chấm than
    excl_tmpl = cv2.imread(EXCLAMATION_TEMPLATE_FILE)
    excl_tmpl_gray = cv2.cvtColor(excl_tmpl, cv2.COLOR_BGR2GRAY)
    eh_ref, ew_ref = excl_tmpl_gray.shape

    # Lấy chiều cao gốc của Nametag từ file để tính tỉ lệ zoom
    th_ref = 15 # Mặc định nếu không có file
    if os.path.exists(NAMETAG_TEMPLATE_FILE):
        nametag_tmpl = cv2.imread(NAMETAG_TEMPLATE_FILE)
        th_ref = nametag_tmpl.shape[0]

    sct = mss.mss()
    monitor = sct.monitors[1]
    screen_w = monitor["width"]
    screen_h = monitor["height"]

    overlay = Overlay()

    print("[+] Bam 'R' de bat dau. Giu 'Q' de thoat.")
    while True:
        if keyboard.is_pressed('r'):
            break
        overlay.update_window()
        time.sleep(0.01)

    print("[+] Tool bat dau chay!")
    cooldown_until = 0

    try:
        while True:
            overlay.update_window()
            if keyboard.is_pressed('q'):
                print("[-] Dang thoat...")
                break

            if time.time() < cooldown_until:
                overlay.draw_boxes(None, None)
                time.sleep(0.05)
                continue

            # Chụp ảnh màn hình
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            # BƯỚC 1: Lọc màu xanh tìm tên nhân vật (Scale-Invariant)
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            lower_green = np.array([35, 100, 100])
            upper_green = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower_green, upper_green)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            detected_nametag = None
            
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = w / float(h)
                if w > 30 and h > 8 and 1.5 < aspect_ratio < 10.0:
                    dist_to_center = abs(x + w/2 - screen_w/2) + abs(y + h/2 - screen_h/2)
                    if detected_nametag is None or dist_to_center < detected_nametag["dist"]:
                        detected_nametag = {"box": (x, y, w, h), "dist": dist_to_center}

            if detected_nametag:
                tx, ty, tw, th = detected_nametag["box"]
                nametag_box = (tx, ty, tw, th)

                # BƯỚC 2: Định vị vùng quét màu xanh dương phía trên đầu
                scan_h_top = int(th * 5.5)
                scan_h_bottom = int(th * 1.5)
                scan_y_start = max(0, ty - scan_h_top)
                scan_y_end = max(0, ty - scan_h_bottom)
                
                margin = int(tw * 0.3)
                scan_x_start = max(0, tx - margin)
                scan_x_end = min(screen_w, tx + tw + margin)
                
                scan_box = (scan_x_start, scan_y_start, scan_x_end - scan_x_start, scan_y_end - scan_y_start)

                if scan_y_end > scan_y_start and scan_x_end > scan_x_start:
                    # Cắt vùng quét để xử lý riêng (giúp tăng tốc độ và tránh nhận diện nhầm bên ngoài)
                    roi_gray = frame_gray[scan_y_start:scan_y_end, scan_x_start:scan_x_end]

                    # BƯỚC 3: Tự động resize ảnh mẫu chấm than theo tỉ lệ zoom của Nametag hiện tại
                    scale = th / float(th_ref)
                    # Giới hạn tỉ lệ tránh resize quá nhỏ hoặc quá lớn gây lỗi
                    scale = max(0.5, min(scale, 2.0))
                    
                    target_w = max(5, int(ew_ref * scale))
                    target_h = max(5, int(eh_ref * scale))
                    
                    # Chỉ thực hiện nếu kích thước vùng quét lớn hơn kích thước template
                    if roi_gray.shape[0] > target_h and roi_gray.shape[1] > target_w:
                        resized_tmpl = cv2.resize(excl_tmpl_gray, (target_w, target_h), interpolation=cv2.INTER_AREA)

                        # BƯỚC 4: Template Matching tìm dấu chấm than trong vùng quét
                        res = cv2.matchTemplate(roi_gray, resized_tmpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)

                        if max_val >= THRESHOLD:
                            # Tính tọa độ thực tế trên màn hình để vẽ khung đỏ debug
                            mx = scan_x_start + max_loc[0]
                            my = scan_y_start + max_loc[1]
                            matched_box = (mx, my, target_w, target_h)
                            
                            overlay.draw_boxes(nametag_box, scan_box, matched_box, max_val)
                            overlay.update_window()

                            print(f"\n[!!!] PHAT HIEN CHINH XAC CHAM THAN! (Khớp: {max_val:.2f})")
                            print("[Action] GIAT CAN!!!")
                            pydirectinput.press('space')
                            
                            cooldown_until = time.time() + 5.0
                            print("---------------------------------------")
                            continue
                
                # Nếu chưa giật cần, vẽ khung xanh lá và xanh dương bình thường
                overlay.draw_boxes(nametag_box, scan_box)
            else:
                overlay.draw_boxes(None, None)

            time.sleep(0.01)

    except Exception as e:
        print(f"[Loi] {e}")

if __name__ == "__main__":
    main()
