import cv2
import numpy as np
import mss
import time
import os
import keyboard
import json

DATASET_DIR = "dataset"
STATES = {
    "0": "0_no_rod",
    "1": "1_ready",
    "2": "2_fishing",
    "3": "3_hooked",
    "4": "4_success",
    "5": "5_broken",
    "6": "6_shadow"
}

def create_folders():
    if not os.path.exists(DATASET_DIR):
        os.makedirs(DATASET_DIR)
    for state_dir in STATES.values():
        path = os.path.join(DATASET_DIR, state_dir)
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"[+] Da tao thu muc: {path}")

def main():
    create_folders()

    print("==================================================")
    print("   CONG CU THU THAP DU LIEU ANH MAU (THU CONG)")
    print("==================================================")
    print("Huong dan chup thu cong:")
    print("  Nhấn các phím số tương ứng với trạng thái để CHỤP:")
    print("    '0' : Chua cam can (0_no_rod)")
    print("    '1' : Sẵn sàng (1_ready)")
    print("    '2' : Đang chờ cá (2_fishing)")
    print("    '3' : Cá cắn câu / Chấm than trên đầu (3_hooked)")
    print("    '4' : Thành công / Đang khoe cá (4_success)")
    print("    '5' : Cần hỏng (5_broken)")
    print("    '6' : Bóng cá / Chấm than gần phao (6_shadow)")
    print("  Phim 'q' : THOAT")
    print("==================================================")

    # --- LOAD CONFIG (Để lấy game_area) ---
    config = {}
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            config = json.load(f)

    game_area = config.get("game_area", None)

    sct = mss.mss()
    
    # Thiết lập khung chụp
    if game_area:
        monitor = {
            "top": game_area["y"],
            "left": game_area["x"],
            "width": game_area["w"],
            "height": game_area["h"]
        }
        print(f"[i] Che do: CHUP TRONG VUNG GAME (x={game_area['x']}, y={game_area['y']}, {game_area['w']}x{game_area['h']})")
    else:
        monitor = sct.monitors[1]
        print(f"[!] Canh bao: CHUA CĂN CỬA SỔ GAME (Chạy calibrate.py và bấm G trước)")
        print(f"[i] Che do: CHUP TOAN MAN HINH ({monitor['width']}x{monitor['height']})")

    print("[+] Bat dau lang nghe phim bam thu cong...")

    while True:
        try:
            # Thoat chuong trinh
            if keyboard.is_pressed('q'):
                print("[-] Dang thoat chuong trinh...")
                break

            # Quet phim tu 0 den 6
            for key in STATES:
                if keyboard.is_pressed(key):
                    # Chup man hinh vung game (hoac toan man hinh)
                    sct_img = sct.grab(monitor)
                    frame = np.array(sct_img)
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    state_folder = STATES[key]
                    filename = f"img_{int(time.time() * 1000)}.png"
                    filepath = os.path.join(DATASET_DIR, state_folder, filename)
                    
                    cv2.imwrite(filepath, frame_bgr)
                    print(f"[OK] Da chup va luu vao: {filepath}")
                    
                    # Tránh bị nhấn đúp phím
                    time.sleep(0.3)

        except KeyboardInterrupt:
            break
        
        # Cho nhe de giam tai CPU
        time.sleep(0.01)

if __name__ == "__main__":
    main()
