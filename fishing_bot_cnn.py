import cv2
import numpy as np
import mss
import time
import os
import json
import pydirectinput
import keyboard
import torch
from torchvision import transforms
from train_cnn import FishingCNN, IMAGE_SIZE

CONFIG_FILE = "config.json"
MODEL_FILE = "fishing_cnn.pth"

DEFAULT_KEYS = {
    "cast_reel": "space",
    "store_fish": "x",
    "repair": "space"
}

STATE_NAMES = {
    0: "Chua cam can (Tam dung cho)",
    1: "Cam can chua tha cau (Ready)",
    2: "Cam can da tha cau (Fishing)",
    3: "CA CAN CAU !!! (Hooked)",
    4: "Cau ca thanh cong (Success)",
    5: "Can bi hong (Broken)",
    6: "Bong ca xuat hien (Shadow!)"
}

def load_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception:
            pass
    if "keys" not in config:
        config["keys"] = DEFAULT_KEYS
    return config

def main():
    print("==================================================")
    print("      BOT CAU CA CNN v4 (FULL AI - RESNET18)")
    print("==================================================")
    print("Huong dan su dung:")
    print(" 1. Thu thap data cho ca 7 thu muc (dac biet la 3_hooked).")
    print(" 2. Chay train_cnn.py de huan luyen ra model ResNet18.")
    print(" 3. Nhan phim 'R' de BAT DAU cau tu dong.")
    print(" 4. Giu phim 'Q' de DUNG / THOAT BOT.")
    print("==================================================")

    config = load_config()
    keys = config.get("keys", DEFAULT_KEYS)
    delay = config.get("delay", 0.05)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[i] Device: {device}")

    if not os.path.exists(MODEL_FILE):
        print(f"[Loi] Khong tim thay model '{MODEL_FILE}'. Vui long chay train_cnn.py truoc.")
        return

    model = FishingCNN(num_classes=7)
    try:
        model.load_state_dict(torch.load(MODEL_FILE, map_location=device))
        model.to(device)
        model.eval()
        print("[+] Nap thanh cong mo hinh CNN 7 class!")
    except Exception as e:
        print(f"[Loi] Khong the nap model: {e}")
        return

    preprocess = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    keyboard.wait('r')
    print("[+] Bot bat dau hoat dong!")
    time.sleep(1)

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

    last_state = -1
    shadow_detected = False
    shadow_start_time = 0
    SHADOW_ALERT_DURATION = 10.0
    SHADOW_SCAN_DELAY = 0.01

    try:
        with torch.no_grad():
            while True:
                if keyboard.is_pressed('q'):
                    print("[-] Nhan Q. Dang thoat bot...")
                    break

                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

                tensor_img = preprocess(frame).unsqueeze(0).to(device)
                outputs = model(tensor_img)
                probabilities = torch.softmax(outputs, dim=1)
                confidence, predicted = torch.max(probabilities, 1)
                state = predicted.item()
                conf = confidence.item()

                if state != last_state:
                    print(f"[CNN] {STATE_NAMES.get(state, 'Khong xac dinh')} (Conf: {conf:.1%})")
                    last_state = state

                # === XU LY TRANG THAI ===
                if state == 0:
                    shadow_detected = False
                    time.sleep(1.0)

                elif state == 1:
                    print("[Action] QUANG CAN...")
                    pydirectinput.press(keys["cast_reel"])
                    shadow_detected = False
                    time.sleep(2.5)

                elif state == 2:
                    if shadow_detected and (time.time() - shadow_start_time < SHADOW_ALERT_DURATION):
                        time.sleep(SHADOW_SCAN_DELAY)
                    else:
                        shadow_detected = False
                        time.sleep(delay)

                elif state == 6:  # Bong ca
                    if not shadow_detected:
                        print("[!!!] BONG CA XUAT HIEN! Che do CANH GIAC CAO!")
                        shadow_detected = True
                        shadow_start_time = time.time()
                    time.sleep(SHADOW_SCAN_DELAY)

                elif state == 3:  # CA CAN CAU
                    print(f"[!!!] CA CAN CAU (Conf: {conf:.1%})! GIAT CAN NGAY!")
                    pydirectinput.press(keys["cast_reel"])
                    shadow_detected = False
                    time.sleep(5.0)

                elif state == 4:
                    print("[Action] Thu hoach ca...")
                    pydirectinput.press(keys["store_fish"])
                    shadow_detected = False
                    time.sleep(1.5)

                elif state == 5:
                    print("[Action] CAN HONG! Sua can...")
                    pydirectinput.press(keys["repair"])
                    shadow_detected = False
                    time.sleep(2.0)

                time.sleep(0.01)

    except Exception as e:
        print(f"[Loi]: {e}")
    finally:
        print("[!] Bot da dung.")

if __name__ == "__main__":
    main()
