import cv2
import numpy as np
import mss
import time
import os
import torch
from torchvision import transforms
from train_cnn import FishingCNN, IMAGE_SIZE
from fishing_bot_cnn import STATE_NAMES

def main():
    print("==================================================")
    print("      CONG CU KIEM THU MANG CNN (TEST CNN)")
    print("==================================================")
    print(" Chuong trinh se chup anh man hinh lien tuc va in ra")
    print(" trang thai du doan tu CNN trong thoi gian thuc.")
    print(" Nhan phim 'q' tai cua so CMD/Terminal de thoat.")
    print("==================================================")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[i] Dang su dung thiet bi: {device}")

    if not os.path.exists("fishing_cnn.pth"):
        print("[Error] Khong tim thay file 'fishing_cnn.pth'. Vui long chay train_cnn.py truoc.")
        return

    model = FishingCNN(num_classes=6)
    try:
        model.load_state_dict(torch.load("fishing_cnn.pth", map_location=device))
        model.to(device)
        model.eval()
        print("[+] Nap thanh cong mo hinh CNN!")
    except Exception as e:
        print(f"[Error] Loi khi load model: {e}")
        return

    preprocess = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    sct = mss.mss()
    monitor = sct.monitors[1]
    
    print("[+] Bat dau quet va kiem thu. Hay chuyen cua so game de kiem tra...")
    time.sleep(1.5)
    
    last_state = -1
    
    try:
        with torch.no_grad():
            while True:
                # Chup anh man hinh
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

                # Tien xu ly va du doan
                tensor_img = preprocess(frame).unsqueeze(0).to(device)
                outputs = model(tensor_img)
                _, predicted = torch.max(outputs, 1)
                state = predicted.item()

                if state != last_state:
                    print(f"[CNN Du doan]: {STATE_NAMES.get(state, 'Khong xac dinh')} (Ma: {state})")
                    last_state = state

                time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n[-] Da dung chuong trinh kiem thu CNN.")

if __name__ == "__main__":
    main()
