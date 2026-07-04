import cv2
import numpy as np
import os
from feature_extractor import StateFeatureExtractor

DATASET_DIR = "dataset"
MODEL_FILE = "trained_model.npz"
STATES = {
    "0_no_rod": 0,
    "1_ready": 1,
    "2_fishing": 2,
    "3_hooked": 3,
    "4_success": 4,
    "5_broken": 5
}

def load_dataset():
    extractor = StateFeatureExtractor()
    features = []
    labels = []
    
    if not os.path.exists(DATASET_DIR):
        print(f"[Error] Thu muc '{DATASET_DIR}' khong ton tai. Vui long chay collect_data.py truoc.")
        return None, None
        
    print("[*] Bat dau doc dataset va trich xuat dac trung...")
    
    for folder_name, label in STATES.items():
        folder_path = os.path.join(DATASET_DIR, folder_name)
        if not os.path.exists(folder_path):
            continue
            
        files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        print(f" - Doc thu muc '{folder_name}': Tim thay {len(files)} anh.")
        
        for file in files:
            img_path = os.path.join(folder_path, file)
            img = cv2.imread(img_path)
            if img is None:
                continue
                
            # Trich xuat vector dac trung
            feat = extractor.extract(img)
            features.append(feat)
            labels.append(label)
            
    if len(features) == 0:
        print("[Error] Khong co anh nao duoc load thanh cong.")
        return None, None
        
    return np.array(features), np.array(labels)

def main():
    X, y = load_dataset()
    if X is None or y is None:
        return
        
    print(f"[+] Load thanh cong {len(X)} anh mau. Vector dac trung co so chieu: {X.shape[1]}")
    
    # Luu lai vao file .npz (Luu database dac trung cho thuat toan KNN gan nhat)
    np.savez(MODEL_FILE, X=X, y=y)
    print(f"[+] Da luu database dac trung thanh cong vao '{MODEL_FILE}'!")
    print("San sang su dung bot voi nhan dien hoc may!")

if __name__ == "__main__":
    main()
