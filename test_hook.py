import cv2
import numpy as np
import mss
import time
import os
import json
import pydirectinput
import keyboard

CONFIG_FILE = "config.json"
NAMETAG_TEMPLATE_FILE = "nametag_template.png"

def main():
    print("==================================================")
    print("      TEST HOOK DETECTOR (MOTION DETECTION)")
    print("==================================================")
    print("Huong dan:")
    print(" 1. Quang can xuong nuoc va cho.")
    print(" 2. Nhan 'R' de bat dau test.")
    print(" 3. Giu 'Q' de thoat.")
    print("==================================================")

    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

    if not os.path.exists(NAMETAG_TEMPLATE_FILE):
        print("[!] LOI: Thieu file nametag_template.png!")
        print("[!] Hay chay calibrate.py va bam 'N' de chup truoc nhe.")
        return

    nametag_tmpl = cv2.imread(NAMETAG_TEMPLATE_FILE)
    nametag_gray = cv2.cvtColor(nametag_tmpl, cv2.COLOR_BGR2GRAY)
    
    scan_height_ratio = config.get("hook_scan_height_ratio", 5.0)
    nametag_threshold = config.get("nametag_threshold", 0.45)

    sct = mss.mss()
    game_area = config.get("game_area", None)
    if game_area:
        monitor = {
            "top": game_area["y"],
            "left": game_area["x"],
            "width": game_area["w"],
            "height": game_area["h"]
        }
    else:
        monitor = sct.monitors[1]

    keyboard.wait('r')
    print("[+] Da bat dau! Dang quet tim cham than bang Motion Detection...")

    cooldown = 0
    history_rois = []
    MAX_HISTORY = 10 # Luu khoang 10 frame gan nhat
    
    try:
        while True:
            if keyboard.is_pressed('q'):
                print("[-] Dang thoat...")
                break

            if time.time() < cooldown:
                time.sleep(0.01)
                history_rois.clear() # Xoa lich su trong luc cooldown
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

                # Lay vung CAO TREN CUNG, bo qua phan duoi de tranh bong ca (ca boi vao roi)
                scan_h_top = int(th * 5.0)
                scan_h_bottom = int(th * 2.0) # Tu 2.0 den 5.0 chieu cao
                scan_y_start = max(0, ty - scan_h_top)
                scan_y_end = max(0, ty - scan_h_bottom)
                
                margin = int(tw * 0.2)
                scan_x_start = max(0, tx - margin)
                scan_x_end = min(frame_bgr.shape[1], tx + tw + margin)

                if scan_y_end > scan_y_start and scan_x_end > scan_x_start:
                    roi = frame_gray[scan_y_start:scan_y_end, scan_x_start:scan_x_end]
                    # Blur de giam nhieu (giam sai so do camera rung nhe hoac nuoc chay)
                    roi_blur = cv2.GaussianBlur(roi, (5, 5), 0)
                    
                    if len(history_rois) == MAX_HISTORY:
                        # Lay frame cu nhat trong queue de so sanh
                        old_roi = history_rois[0]
                        diff = cv2.absdiff(roi_blur, old_roi)
                        
                        # Threshold de tim thay doi thuc su khac biet
                        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                        changed_pixels = cv2.countNonZero(thresh)
                        
                        # Neu luong pixel thay doi lon hon mot nguong nao do
                        if changed_pixels > 50:
                            print(f"\n[!!!] PHAT HIEN SU XUAT HIEN DOT NGOT! (Pixels: {changed_pixels})")
                            print("[Action] GIAT CAN NGAY!")
                            pydirectinput.press('space')
                            cooldown = time.time() + 5.0
                            print("---------------------------------------")
                            history_rois.clear()
                            continue
                            
                    # Cap nhat history
                    history_rois.append(roi_blur)
                    if len(history_rois) > MAX_HISTORY:
                        history_rois.pop(0)

            # Quet voi FPS ~20
            time.sleep(0.05)

    except Exception as e:
        print(f"[Loi] {e}")

if __name__ == "__main__":
    main()
