import cv2
import numpy as np
import mss
import time
import json
import os
import pydirectinput
import keyboard

CONFIG_FILE = "config.json"
# Thiet lap do tre giua cac lenh click ve 0 de giat can tuc thi
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = True

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    print("[Error] Khong tim thay file config.json. Vui long chay calibrate.py truoc.")
    exit(1)

def detect_red_exclamation(img):
    """
    Nhan dien mau do cua dau cham than trong anh chup vung theo doi (ROI).
    Tra ve True neu so pixel mau do vuot qua nguong (red_threshold).
    """
    # Chuyen anh sang he mau HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Dai mau do trong HSV chia lam 2 phan (mo rong dai mau do de nhay hon)
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    # Gop 2 mask mau do lai
    mask = mask1 + mask2
    
    # Dem so luong pixel mau do
    red_pixel_count = np.sum(mask > 0)
    return red_pixel_count

def main():
    config = load_config()
    
    fish_btn = config["fish_btn"]
    cast_btn = config["cast_btn"]
    watch_area = config["watch_area"]
    delay = config["delay"]
    red_threshold = config.get("red_threshold", 50)
    
    print("==================================================")
    print("       BOT CAU CA PLAY TOGETHER KHOI DONG")
    print("==================================================")
    print(f" - Nut bam: {fish_btn}")
    print(f" - Vung quet: {watch_area}")
    print(f" - Nguong pixel do: {red_threshold}")
    print("--------------------------------------------------")
    print("Huong dan su dung:")
    print(" 1. Hay dung tai vi tri cau ca, cam san can tren tay.")
    print(" 2. Nhan phim 'R' de bat dau chay tu dong.")
    print(" 3. Giu hoac nhan phim 'Q' de TAM DUNG / THOAT BOT.")
    print("==================================================")

    # Cho lenh bat dau
    keyboard.wait('r')
    print("[+] Bot bat dau hoat dong!")
    time.sleep(1)

    sct = mss.mss()
    
    # Dinh nghia vung chup anh (monitor) dua tren config
    monitor = {
        "top": watch_area["y"],
        "left": watch_area["x"],
        "width": watch_area["w"],
        "height": watch_area["h"]
    }

    try:
        while True:
            if keyboard.is_pressed('q'):
                print("[-] Da nhan Q. Dang dung bot...")
                break
                
            # --- BUOC 1: QUANG CAN ---
            print("[+] Dang quang can...")
            pydirectinput.click(cast_btn[0], cast_btn[1])
            
            # Cho phao cau roi xuong nuoc va on dinh (khoang 2-3 giay tuy loai can)
            time.sleep(2.5)
            
            # --- BUOC 2: CHO CA CAN ---
            print("[*] Dang cho ca can (dang quet dau chấm than)...")
            fish_bited = False
            
            # Reset bo dem thoi gian de tranh bot bi ket neu ca khong can qua lau (vidu 40s)
            start_wait_time = time.time()
            
            while time.time() - start_wait_time < 45:
                if keyboard.is_pressed('q'):
                    break
                
                # Chup anh vung theo doi
                sct_img = sct.grab(monitor)
                # Chuyen doi sang dinh dang anh OpenCV
                frame = np.array(sct_img)
                # BGR vi mss tra ve BGRA
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Kiem tra mau do
                red_pixels = detect_red_exclamation(frame)
                
                if red_pixels > 0:
                    print(f"-> Phat hien: {red_pixels} px do (Nguong: {red_threshold})")
                
                if red_pixels > red_threshold:
                    print(f"[!!!] CA CAN CAU! Phat hien {red_pixels} pixel do.")
                    fish_bited = True
                    break
                
                time.sleep(delay)
            
            # --- BUOC 3: GIAT CAN VA THU HOACH ---
            if fish_bited:
                # Giat can ngay lap tuc
                pydirectinput.click(fish_btn[0], fish_btn[1])
                print("[+] Da giat can! Cho animation hoan thanh...")
                
                # Cho animation keo ca va bang thong bao ca hien ra (khoang 5-6 giay)
                time.sleep(5.5)
                
                # Click de dong thong bao nhan ca (cay/tui do)
                print("[+] Click thu hoach (dong bang thong bao)...")
                pydirectinput.click(fish_btn[0], fish_btn[1])
                
                # Cho 2 giay de game ve trang thai binh thuong
                time.sleep(2.0)
            else:
                print("[-] Het thoi gian cho hoac bi ngat. Thu quang can lai...")
                # De phong can bi thu hoi, click mot cai cho chac
                pydirectinput.click(fish_btn[0], fish_btn[1])
                time.sleep(2.0)

    except Exception as e:
        print(f"[Error] Co loi xay ra: {e}")
    finally:
        print("[!] Bot da dung. Cam on ban da su dung!")

if __name__ == "__main__":
    main()
