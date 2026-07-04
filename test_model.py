import cv2
import numpy as np
import mss
import time
import os
from feature_extractor import StateFeatureExtractor
from fishing_bot_ml import KNNClassifier, STATE_NAMES

def main():
    print("==================================================")
    print("      CONG CU KIEM THU MO HINH (TEST MODEL)")
    print("==================================================")
    print(" Chuong trinh se chup anh man hinh lien tuc va in ra")
    print(" trang thai du doan trong thoi gian thuc.")
    print(" Nhan phim 'q' tai cua so CMD/Terminal de thoat.")
    print("==================================================")

    if not os.path.exists("trained_model.npz"):
        print("[Error] Khong tim thay file 'trained_model.npz'. Vui long chay train_model.py truoc.")
        return

    try:
        classifier = KNNClassifier("trained_model.npz")
    except Exception as e:
        print(f"[Error] Loi khi load model: {e}")
        return

    extractor = StateFeatureExtractor()
    sct = mss.mss()
    monitor = sct.monitors[1]
    
    print("[+] Bat dau quet va kiem thu. Hay chuyen cua so game de kiem tra...")
    time.sleep(1.5)
    
    last_state = -1
    
    try:
        while True:
            # Chup anh man hinh
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            # Trich xuat dac trung va du doan
            feat = extractor.extract(frame)
            state = classifier.predict(feat, k=1)

            if state != last_state:
                print(f"[Du doan]: {STATE_NAMES.get(state, 'Khong xac dinh')} (Ma: {state})")
                last_state = state

            # Nghi mot khoang ngan de tranh qua tai CPU
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n[-] Da dung chuong trinh kiem thu.")

if __name__ == "__main__":
    main()
