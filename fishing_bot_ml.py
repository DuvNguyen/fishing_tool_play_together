import cv2
import numpy as np
import mss
import time
import os
import json
import pydirectinput
import keyboard
from feature_extractor import StateFeatureExtractor

CONFIG_FILE = "config.json"
MODEL_FILE = "trained_model.npz"

# Cấu hình phím bấm
# Người dùng có thể cấu hình thêm trong config.json
DEFAULT_KEYS = {
    "cast_reel": "space",  # Thả câu và giật cần
    "store_fish": "x",     # Phím bảo quản cá (để tiếp tục câu)
    "repair": "space"      # Phím sửa cần hoặc phím hành động bất kỳ
}

STATE_NAMES = {
    0: "Chua cam can (Tam dung cho)",
    1: "Cam can chua tha cau (Ready)",
    2: "Cam can da tha cau (Fishing)",
    3: "Ca dinh cau (Hooked!)",
    4: "Cau ca thanh cong (Success)",
    5: "Can bi hong (Broken)"
}

class KNNClassifier:
    def __init__(self, model_path=MODEL_FILE):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Khong tim thay file model '{model_path}'. Vui long chay train_model.py truoc.")
        data = np.load(model_path)
        self.X = data['X']
        self.y = data['y']
        print(f"[+] Loaded database voi {len(self.X)} anh mau.")

    def predict(self, feat, k=1):
        """Dự đoán trạng thái dựa trên khoảng cách Euclidean gần nhất (KNN)"""
        # Tinh khoang cach tu feat hien tai den toan bo tap du lieu
        dists = np.linalg.norm(self.X - feat, axis=1)
        # Lay k index gan nhat
        nearest_indices = np.argsort(dists)[:k]
        nearest_labels = self.y[nearest_indices]
        # Bieu quyet label
        counts = np.bincount(nearest_labels)
        return np.argmax(counts)

def load_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception:
            pass
    # Them phan cau hinh key neu chua co
    if "keys" not in config:
        config["keys"] = DEFAULT_KEYS
    return config

def main():
    print("==================================================")
    print("      BOT CAU CA HOC MAY (MACHINE LEARNING)")
    print("==================================================")
    print("Huong dan su dung:")
    print(" 1. Hay dam bao da chay train_model.py de co model.")
    print(" 2. Nhan phan 'R' de BAT DAU.")
    print(" 3. Giu phim 'Q' de DUNG / THOAT BOT.")
    print("==================================================")

    config = load_config()
    keys = config.get("keys", DEFAULT_KEYS)
    delay = config.get("delay", 0.05)

    # Load bo phan lop KNN va Feature Extractor
    try:
        classifier = KNNClassifier(MODEL_FILE)
    except Exception as e:
        print(e)
        return

    extractor = StateFeatureExtractor()

    # Cho lenh bat dau
    keyboard.wait('r')
    print("[+] Bot bat dau hoat dong!")
    time.sleep(1)

    sct = mss.mss()
    monitor = sct.monitors[1]
    last_state = -1

    try:
        while True:
            if keyboard.is_pressed('q'):
                print("[-] Nhan Q. Dang thoat bot...")
                break

            # 1. Chup anh man hinh
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            # 2. Trich xuat dac trung va du doan trang thai
            feat = extractor.extract(frame)
            state = classifier.predict(feat, k=1)

            if state != last_state:
                print(f"[Trang thai]: {STATE_NAMES.get(state, 'Khong xac dinh')}")
                last_state = state

            # 3. Thuc hien hanh dong dua tren trang thai
            if state == 0:
                # Chua cam can: dung moi hoat dong cho den khi cam can
                time.sleep(1.0)
                
            elif state == 1:
                # Cam can chua tha cau: an nut tha cau (space)
                print("[Action] Thuc hien QUANG CAN...")
                pydirectinput.press(keys["cast_reel"])
                time.sleep(2.5)  # Cho can roi xuong nuoc va phao on dinh
                
            elif state == 2:
                # Dang cau: cho ca bit
                time.sleep(delay)
                
            elif state == 3:
                # Ca dinh cau: giat can ngay lap tuc
                print("[Action] CA DINH CAU! Dang GIAT CAN...")
                pydirectinput.press(keys["cast_reel"])
                time.sleep(5.0)  # Cho animation keo ca
                
            elif state == 4:
                # Cau ca thanh cong (hien thi thong bao): nhan nut bao quan de tiep tuc
                print("[Action] Thu hoach ca (Bao quan)...")
                pydirectinput.press(keys["store_fish"])
                time.sleep(1.5)
                
            elif state == 5:
                # Can bi hong: thuc hien nut sua can (hoac space de tiep tuc neu game hien hop thoai sua)
                print("[Action] CAN HONG! Dang bam sua can...")
                pydirectinput.press(keys["repair"])
                time.sleep(2.0)

            time.sleep(0.01)

    except Exception as e:
        print(f"[Loi]: {e}")
    finally:
        print("[!] Bot da dung.")

if __name__ == "__main__":
    main()
