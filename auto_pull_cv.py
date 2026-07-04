import cv2
import numpy as np
import mss
import time
import os
import pydirectinput
import keyboard

EXCLAMATION_TEMPLATE_FILE = "exclamation.png"
THRESHOLD = 0.8  # Độ nhạy (từ 0.0 đến 1.0). Càng cao càng cần giống y hệt mẫu.

def main():
    print("==================================================")
    print("      AUTO-PULL (OPENCV TEMPLATE MATCHING)")
    print("==================================================")
    print("Huong dan su dung:")
    print(" 1. Ban can chup 1 anh cai dau cham than luc ca can cau.")
    print(" 2. Cat (Crop) rieng cai dau cham than do, luu ten 'exclamation.png'.")
    print(" 3. De file 'exclamation.png' chung thu muc voi file nay.")
    print(" 4. Quang can xuong nuoc va Nhan phim 'R' de bat dau Auto-Pull.")
    print(" 5. Giu phim 'Q' de thoat.")
    print("==================================================")

    if not os.path.exists(EXCLAMATION_TEMPLATE_FILE):
        print(f"[!] LOI: Khong tim thay file '{EXCLAMATION_TEMPLATE_FILE}'!")
        print("Vui long cat anh dau cham than va luu vao thu muc truoc.")
        return

    # Load template
    template = cv2.imread(EXCLAMATION_TEMPLATE_FILE)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    tw, th = template_gray.shape[::-1]

    sct = mss.mss()
    monitor = sct.monitors[1]  # Chup toan man hinh (man hinh chinh)

    keyboard.wait('r')
    print("[+] Tool da chay! Dang quet tim dau cham than...")

    cooldown_until = 0

    try:
        while True:
            # Nhan Q de thoat
            if keyboard.is_pressed('q'):
                print("[-] Da thoat tool.")
                break

            # Neu dang trong thoi gian cooldown sau khi giat, thi bo qua
            if time.time() < cooldown_until:
                time.sleep(0.05)
                continue

            # Chup man hinh
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

            # Tim dau cham than tren man hinh
            res = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= THRESHOLD:
                print(f"[!!!] PHAT HIEN DAU CHAM THAN! (Do chinh xac: {max_val:.2f})")
                print("[Action] GIAT CAN NGAY!")
                pydirectinput.press('space')
                
                # Cooldown 5 giay de khong bi bam space lien tuc (cho hoat anh giat can xong)
                cooldown_until = time.time() + 5.0
                print("---------------------------------------")

            # Ngu nghi 0.01s (tuc la chay khoang 100 fps) de tiet kiem CPU
            time.sleep(0.01)

    except Exception as e:
        print(f"[Loi] {e}")

if __name__ == "__main__":
    main()
