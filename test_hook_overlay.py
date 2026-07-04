import cv2
import numpy as np
import mss
import time
import os
import json
import pydirectinput
import keyboard
import tkinter as tk
import threading

CONFIG_FILE = "config.json"
NAMETAG_TEMPLATE_FILE = "nametag_template.png"

class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "black")
        
        # Cho phép click chuột xuyên qua cửa sổ overlay (Windows only)
        try:
            self.root.wm_attributes("-disabled", True)
        except:
            pass

        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+0+0")
        
        self.canvas = tk.Canvas(self.root, width=w, height=h, bg="black", highlightthickness=0)
        self.canvas.pack()
        
    def draw_boxes(self, nametag_box, scan_box):
        self.canvas.delete("all")
        if nametag_box:
            x, y, w, h = nametag_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#00FF00", width=3)
        if scan_box:
            x, y, w, h = scan_box
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#0000FF", width=3)
            
    def update_window(self):
        self.root.update()

def main():
    print("==================================================")
    print("      TEST HOOK DETECTOR (CO OVERLAY TRONG GAME)")
    print("==================================================")

    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

    if not os.path.exists(NAMETAG_TEMPLATE_FILE):
        print("[!] LOI: Thieu file nametag_template.png!")
        return

    nametag_tmpl = cv2.imread(NAMETAG_TEMPLATE_FILE)
    nametag_gray = cv2.cvtColor(nametag_tmpl, cv2.COLOR_BGR2GRAY)
    
    nametag_threshold = config.get("nametag_threshold", 0.45)

    sct = mss.mss()
    monitor = sct.monitors[1] # Man hinh chinh

    # Khoi tao overlay
    overlay = Overlay()

    print("[+] Bam 'R' de bat dau quet.")
    print("[+] Giu 'Q' de thoat.")
    
    while True:
        if keyboard.is_pressed('r'):
            break
        overlay.update_window()
        time.sleep(0.01)

    print("[+] Da bat dau!")

    cooldown = 0
    history_rois = []
    MAX_HISTORY = 10
    
    try:
        while True:
            # 1. Update giao dien overlay hien tai
            overlay.update_window()
            
            if keyboard.is_pressed('q'):
                print("[-] Dang thoat...")
                break

            if time.time() < cooldown:
                time.sleep(0.01)
                history_rois.clear()
                overlay.draw_boxes(None, None) # An khung luc cooldown
                continue

            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            res_nametag = cv2.matchTemplate(frame_gray, nametag_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val_tag, _, max_loc_tag = cv2.minMaxLoc(res_nametag)

            if max_val_tag >= nametag_threshold:
                tx, ty = max_loc_tag
                tw, th = nametag_tmpl.shape[1], nametag_tmpl.shape[0]

                scan_h_top = int(th * 5.0)
                scan_h_bottom = int(th * 2.0)
                scan_y_start = max(0, ty - scan_h_top)
                scan_y_end = max(0, ty - scan_h_bottom)
                
                margin = int(tw * 0.2)
                scan_x_start = max(0, tx - margin)
                scan_x_end = min(frame_bgr.shape[1], tx + tw + margin)
                
                # Update overlay ngay tren game
                nametag_box = (tx, ty, tw, th)
                scan_box = (scan_x_start, scan_y_start, scan_x_end - scan_x_start, scan_y_end - scan_y_start)
                overlay.draw_boxes(nametag_box, scan_box)

                if scan_y_end > scan_y_start and scan_x_end > scan_x_start:
                    roi = frame_gray[scan_y_start:scan_y_end, scan_x_start:scan_x_end]
                    roi_blur = cv2.GaussianBlur(roi, (5, 5), 0)
                    
                    if len(history_rois) == MAX_HISTORY:
                        old_roi = history_rois[0]
                        if old_roi.shape == roi_blur.shape:
                            diff = cv2.absdiff(roi_blur, old_roi)
                            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                            changed_pixels = cv2.countNonZero(thresh)
                            
                            if changed_pixels > 50:
                                print(f"\n[!!!] PHAT HIEN SU XUAT HIEN DOT NGOT! (Pixels: {changed_pixels})")
                                pydirectinput.press('space')
                                cooldown = time.time() + 5.0
                                history_rois.clear()
                                continue
                        else:
                            history_rois.clear()
                            
                    history_rois.append(roi_blur)
                    if len(history_rois) > MAX_HISTORY:
                        history_rois.pop(0)
            else:
                # Neu khong thay nametag thi xoa khung
                overlay.draw_boxes(None, None)

            time.sleep(0.01) # Quet nhanh hon

    except Exception as e:
        print(f"[Loi] {e}")

if __name__ == "__main__":
    main()
