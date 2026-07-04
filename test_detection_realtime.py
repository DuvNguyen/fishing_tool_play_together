import cv2
import numpy as np
import mss
import time
import os
import keyboard
import tkinter as tk
import ctypes
from ctypes import wintypes

EXCLAMATION_TEMPLATE_FILE = "exclamation_template.png"
NAMETAG_TEMPLATE_FILE = "nametag_template.png"

# Ngưỡng khớp lệnh
NAMETAG_THRESHOLD = 0.60     # Nâng lên để giảm false positive
EXCLAMATION_THRESHOLD = 0.55  # Nhận diện dấu chấm than

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

WindowFromPoint = ctypes.windll.user32.WindowFromPoint
WindowFromPoint.argtypes = [POINT]
WindowFromPoint.restype = wintypes.HWND

GetWindowRect = ctypes.windll.user32.GetWindowRect
GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
GetWindowRect.restype = wintypes.BOOL

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
        
    def draw_boxes(self, nametag_box, scan_box, matched_box=None, score=0.0, tracking=False, name_score=0.0, estimated=False):
        self.canvas.delete("all")
        if nametag_box:
            x, y, w, h = nametag_box
            if estimated:
                color = "#FF9900"  # Màu cam nếu đang ước lượng vị trí (khi tên bị ẩn)
                status = "Estimated (Hidden)"
            else:
                color = "#00FF00" if tracking else "#FFFF00"
                status = f"Locked: {name_score:.2f}"
            
            self.canvas.create_rectangle(x, y, x+w, y+h, outline=color, width=2)
            self.canvas.create_text(x, y-10, text=f"ngducvii ({status})", fill=color, anchor="w")
        if scan_box:
            x, y, w, h = scan_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#0000FF", width=2)
        if matched_box:
            mx, my, mw, mh = matched_box
            self.canvas.create_rectangle(mx, my, mx+mw, my+mh, outline="#FF0000", width=3)
            self.canvas.create_text(mx, my-12, text=f"HOOKED! Score: {score:.2f}", fill="#FF0000", anchor="w")
            
    def update_window(self):
        self.root.update()

def find_nametag_center_bias(img_gray, template_gray, scales=[0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]):
    """Tìm nametag ưu tiên vị trí gần tâm màn hình, loại bỏ false positive góc."""
    h_img, w_img = img_gray.shape
    cx, cy = w_img / 2.0, h_img / 2.0
    max_dist = (cx**2 + cy**2) ** 0.5
    PENALTY_WEIGHT = 0.15

    best_score, best_loc, best_scale = -1.0, None, 1.0
    th, tw = template_gray.shape
    for scale in scales:
        resized_w = int(tw * scale)
        resized_h = int(th * scale)
        if img_gray.shape[0] < resized_h or img_gray.shape[1] < resized_w:
            continue
        resized_tmpl = cv2.resize(template_gray, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(img_gray, resized_tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        match_cx = max_loc[0] + resized_w / 2.0
        match_cy = max_loc[1] + resized_h / 2.0
        dist = ((match_cx - cx)**2 + (match_cy - cy)**2) ** 0.5
        penalty = PENALTY_WEIGHT * (dist / max_dist)
        adjusted = max_val - penalty
        if adjusted > best_score:
            best_score, best_loc, best_scale = adjusted, max_loc, scale
    return best_score, best_loc, best_scale

def find_exclamation_multiscale(roi_gray, template_gray, base_scale, scale_offsets=[0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]):
    best_val = -1.0
    best_loc = None
    best_w, best_h = 0, 0
    
    th, tw = template_gray.shape
    for offset in scale_offsets:
        scale = base_scale * offset
        scale = max(0.4, min(scale, 2.2))
        
        resized_w = int(tw * scale)
        resized_h = int(th * scale)
        
        if roi_gray.shape[0] < resized_h or roi_gray.shape[1] < resized_w:
            continue
            
        resized_tmpl = cv2.resize(template_gray, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(roi_gray, resized_tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_w = resized_w
            best_h = resized_h
            
    return best_val, best_loc, best_w, best_h

def find_game_window(ref_x, ref_y):
    target_hwnd = None
    def foreach_window(hwnd, lParam):
        nonlocal target_hwnd
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if "play together" in title or "ldplayer" in title or "bluestacks" in title or "noxplayer" in title:
                    target_hwnd = hwnd
                    return False
        return True

    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    EnumWindows(EnumWindowsProc(foreach_window), 0)
    
    if target_hwnd:
        return target_hwnd
    pt = POINT(ref_x, ref_y)
    return WindowFromPoint(pt)

def main():
    print("==================================================")
    print("      REALTIME TRACKER (AUTO FALLBACK FOR HIDDEN)")
    print("==================================================")
    print("Mô tả sửa lỗi:")
    print(" - Khi cá cắn câu, tên nhân vật (nametag) thường bị ẩn đi.")
    print(" - Bot sẽ tự động sử dụng tọa độ tương đối đã lưu (Offset) để giữ vùng quét.")
    print(" - Nhờ đó vẫn quét được dấu chấm (!) bình thường kể cả khi tên bị biến mất.")
    print("==================================================")

    if not os.path.exists(NAMETAG_TEMPLATE_FILE) or not os.path.exists(EXCLAMATION_TEMPLATE_FILE):
        print("[Loi] Thieu file template.")
        return

    nametag_tmpl = cv2.imread(NAMETAG_TEMPLATE_FILE)
    nametag_tmpl_gray = cv2.cvtColor(nametag_tmpl, cv2.COLOR_BGR2GRAY)
    th_ref, tw_ref = nametag_tmpl_gray.shape

    excl_tmpl = cv2.imread(EXCLAMATION_TEMPLATE_FILE)
    excl_tmpl_gray = cv2.cvtColor(excl_tmpl, cv2.COLOR_BGR2GRAY)

    sct = mss.mss()
    screen_info = sct.monitors[1]
    screen_w = screen_info["width"]
    screen_h = screen_info["height"]

    # Xác định cửa sổ game để lấy offset
    hwnd = find_game_window(screen_w // 2, screen_h // 2)

    overlay = Overlay()
    keyboard.wait('r')
    print("[+] Bắt đầu quét...")

    last_nametag_box = None
    tracking_margin = 150

    # Lưu trữ tọa độ tương đối của nametag so với cửa sổ game
    last_known_offset_x = None
    last_known_offset_y = None
    last_known_scale = 1.0

    try:
        while True:
            overlay.update_window()
            if keyboard.is_pressed('q'):
                break

            # Lấy vị trí cửa sổ game hiện tại
            rect_curr = wintypes.RECT()
            GetWindowRect(hwnd, ctypes.byref(rect_curr))
            wx = rect_curr.left
            wy = rect_curr.top

            # Xác định vùng chụp màn hình
            if last_nametag_box is None:
                monitor = {"top": 0, "left": 0, "width": screen_w, "height": screen_h}
                offset_x, offset_y = 0, 0
                is_tracking = False
            else:
                lx, ly, lw, lh = last_nametag_box
                monitor = {
                    "top": max(0, ly - tracking_margin),
                    "left": max(0, lx - tracking_margin),
                    "width": min(screen_w - max(0, lx - tracking_margin), lw + 2 * tracking_margin),
                    "height": min(screen_h - max(0, ly - tracking_margin), lh + 2 * tracking_margin)
                }
                offset_x = monitor["left"]
                offset_y = monitor["top"]
                is_tracking = True

            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

            # Tìm kiếm nametag (center-bias để tránh false positive góc màn hình)
            name_score, name_loc, name_scale = find_nametag_center_bias(frame_gray, nametag_tmpl_gray)

            nametag_box_abs = None
            is_estimated = False

            if name_score >= NAMETAG_THRESHOLD:
                # 1. Tìm thấy tên -> Lưu lại tọa độ tương đối so với cửa sổ game
                tx_rel, ty_rel = name_loc
                tw_curr = int(tw_ref * name_scale)
                th_curr = int(th_ref * name_scale)
                
                tx_abs = tx_rel + offset_x
                ty_abs = ty_rel + offset_y
                nametag_box_abs = (tx_abs, ty_abs, tw_curr, th_curr)
                
                # Cập nhật vị trí tracking và offset
                last_nametag_box = nametag_box_abs
                last_known_offset_x = tx_abs - wx
                last_known_offset_y = ty_abs - wy
                last_known_scale = name_scale
            else:
                # 2. Không tìm thấy tên (Bị ẩn) -> Sử dụng tọa độ tương đối đã lưu trước đó
                if last_known_offset_x is not None:
                    tx_abs = wx + last_known_offset_x
                    ty_abs = wy + last_known_offset_y
                    tw_curr = int(tw_ref * last_known_scale)
                    th_curr = int(th_ref * last_known_scale)
                    nametag_box_abs = (tx_abs, ty_abs, tw_curr, th_curr)
                    name_scale = last_known_scale
                    is_estimated = True
                    
                    # Giữ nguyên tracking box tại vị trí ước lượng để frame sau quét nhanh hơn
                    last_nametag_box = nametag_box_abs
                else:
                    # Chưa từng lưu offset -> Bắt buộc reset để quét lại toàn màn hình
                    last_nametag_box = None

            if nametag_box_abs is not None:
                # Tính toán vùng quét dấu chấm than dựa trên vị trí (thực tế hoặc ước lượng)
                tx_rel_mapped = nametag_box_abs[0] - offset_x
                ty_rel_mapped = nametag_box_abs[1] - offset_y
                tw_curr = nametag_box_abs[2]
                th_curr = nametag_box_abs[3]

                scan_h_top = int(th_curr * 3.5)
                scan_h_bottom = int(th_curr * 0.2)
                scan_y_start_rel = max(0, ty_rel_mapped - scan_h_top)
                scan_y_end_rel = max(0, ty_rel_mapped - scan_h_bottom)
                
                margin = int(tw_curr * 0.6)
                scan_x_start_rel = max(0, tx_rel_mapped - margin)
                scan_x_end_rel = min(monitor["width"], tx_rel_mapped + tw_curr + margin)

                scan_box_abs = (
                    scan_x_start_rel + offset_x, 
                    scan_y_start_rel + offset_y, 
                    scan_x_end_rel - scan_x_start_rel, 
                    scan_y_end_rel - scan_y_start_rel
                )

                matched_box = None
                max_val = 0.0

                if scan_y_end_rel > scan_y_start_rel and scan_x_end_rel > scan_x_start_rel:
                    roi_gray = frame_gray[scan_y_start_rel:scan_y_end_rel, scan_x_start_rel:scan_x_end_rel]

                    max_val, excl_loc, target_w, target_h = find_exclamation_multiscale(
                        roi_gray, excl_tmpl_gray, name_scale
                    )

                    if max_val >= 0.1:
                        print(f"Khớp chấm than: {max_val:.2f} (Tên ẩn: {is_estimated})      ", end="\r")

                    if max_val >= EXCLAMATION_THRESHOLD:
                        mx_abs = scan_box_abs[0] + excl_loc[0]
                        my_abs = scan_box_abs[1] + excl_loc[1]
                        matched_box = (mx_abs, my_abs, target_w, target_h)

                overlay.draw_boxes(nametag_box_abs, scan_box_abs, matched_box, max_val, tracking=is_tracking, name_score=name_score, estimated=is_estimated)
            else:
                overlay.draw_boxes(None, None)

            time.sleep(0.02)

    except Exception as e:
        print(f"[Loi] {e}")
    finally:
        overlay.draw_boxes(None, None)

if __name__ == "__main__":
    main()
