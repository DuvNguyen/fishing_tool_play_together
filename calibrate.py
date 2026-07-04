import json
import time
import os
import keyboard
import cv2
import numpy as np
import mss

CONFIG_FILE = "config.json"
TEMPLATE_FILE = "exclamation_template.png"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print(f"\n[+] Da luu cau hinh vao {CONFIG_FILE}!")

def select_area_via_roi(window_title, instruction_msg):
    print(f"\n[!] Chuan bi chup man hinh trong 0.5s...")
    time.sleep(0.5)
    
    sct = mss.mss()
    monitor = sct.monitors[1]
    sct_img = sct.grab(monitor)
    img = np.array(sct_img)
    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    print(f"[!] {instruction_msg}")
    print("    -> Nhan ENTER hoac SPACE de xac nhan. Nhan C de huy.")
    
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_title, cv2.WND_PROP_TOPMOST, 1)
    
    roi = cv2.selectROI(window_title, img_bgr, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_title)
    for _ in range(10):
        cv2.waitKey(1)
        
    if roi[2] > 0 and roi[3] > 0:
        return {"x": int(roi[0]), "y": int(roi[1]), "w": int(roi[2]), "h": int(roi[3])}
    return None

def main():
    print("==================================================")
    print("       CONG CU HIEU CHINH TOA DO BOT CAU CA")
    print("==================================================")
    print("Huong dan phím tat (khong bi trung phim game):")
    print("  'G' : CHON VUNG CUA SO GAME (Gia lap)")
    print("  'H' : KEO CHON VUNG HOOKED (Vung dau nhan vat)")
    print("  'S' : KEO CHON VUNG SHADOW (Vung phao/bong ca)")
    print("  'K' : KEO CHON VUNG TIM NAMETAG (Gioi han vung quet ten nhan vat)")
    print("  'T' : CHUP TEMPLATE dau cham than '!'")
    print("  'N' : CHUP TEMPLATE NAMETAG nhan vat (bubble ten)")
    print("  ESC : Luu va thoat")
    print("==================================================")

    config = load_config()
    
    game_area = config.get("game_area", None)
    watch_area = config.get("watch_area", None)
    watch_area_shadow = config.get("watch_area_shadow", None)
    nametag_area = config.get("nametag_area", None)

    print("\nCau hinh hien tai:")
    print(f"  VUNG GAME  : {game_area if game_area else 'CHUA CO (bam G)'}")
    print(f"  HOOKED     : {watch_area if watch_area else 'CHUA CO (bam H)'}")
    print(f"  SHADOW     : {watch_area_shadow if watch_area_shadow else 'CHUA CO (bam S)'}")
    print(f"  VUNG NAME  : {nametag_area if nametag_area else 'CHUA CO (bam K)'}")
    print(f"  Template ! : {'CO' if os.path.exists(TEMPLATE_FILE) else 'CHUA CO (bam T)'}")
    print(f"  Nametag    : {'CO' if os.path.exists('nametag_template.png') else 'CHUA CO (bam N)'}")
    print("\nDang cho ban bam phim...\n")

    while True:
        try:
            if keyboard.is_pressed('g'):
                area = select_area_via_roi(
                    "CHON VUNG CUA SO GAME",
                    "Dung chuot keo hinh chu nhat quanh CUA SO GAME (vung gia lap)"
                )
                if area:
                    game_area = area
                    print(f"[OK] Vung game da chon: {game_area}")
                else:
                    print("[!] Da huy chon vung game.")
                time.sleep(0.5)

            elif keyboard.is_pressed('k'):
                area = select_area_via_roi(
                    "CHON VUNG TIM NAMETAG",
                    "Dung chuot keo vung quanh vi tri ten nhan vat cua ban hay dung yen"
                )
                if area:
                    nametag_area = area
                    print(f"[OK] Vung tim nametag da chon: {nametag_area}")
                else:
                    print("[!] Da huy chon vung tim nametag.")
                time.sleep(0.5)

            elif keyboard.is_pressed('h'):
                area = select_area_via_roi(
                    "CHON VUNG HOOKED (TREN DAU)",
                    "Dung chuot keo vung tren dau nhan vat (vung se hien '!' hooked)"
                )
                if area:
                    watch_area = area
                    print(f"[OK] Vung HOOKED da chon: {watch_area}")
                else:
                    print("[!] Da huy chon vung HOOKED.")
                time.sleep(0.5)

            elif keyboard.is_pressed('s'):
                area = select_area_via_roi(
                    "CHON VUNG SHADOW (PHAO CA)",
                    "Dung chuot keo vung gan phao cau (vung se hien '!' shadow)"
                )
                if area:
                    watch_area_shadow = area
                    print(f"[OK] Vung SHADOW da chon: {watch_area_shadow}")
                else:
                    print("[!] Da huy chon vung SHADOW.")
                time.sleep(0.5)

            elif keyboard.is_pressed('t'):
                print("\n[!] Chuan bi chup man hinh trong 0.5s...")
                time.sleep(0.5)
                
                sct = mss.mss()
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                win_title = "CHAP TEMPLATE CHAM THAN (!)"
                print("[!] Dung chuot KEO CHAT quanh dau cham than '!' de lay mau")
                print("    Nhan ENTER/SPACE de xac nhan. Nhan C de huy.")
                
                cv2.namedWindow(win_title, cv2.WINDOW_NORMAL)
                cv2.setWindowProperty(win_title, cv2.WND_PROP_TOPMOST, 1)
                
                roi = cv2.selectROI(win_title, img_bgr, fromCenter=False, showCrosshair=True)
                cv2.destroyWindow(win_title)
                for _ in range(10):
                    cv2.waitKey(1)
                
                if roi[2] > 0 and roi[3] > 0:
                    rx, ry, rw, rh = roi
                    template = img_bgr[ry:ry+rh, rx:rx+rw]
                    cv2.imwrite(TEMPLATE_FILE, template)
                    print(f"[OK] Da luu file template -> '{TEMPLATE_FILE}'")
                else:
                    print("[!] Da huy chup template.")
                time.sleep(0.5)

            elif keyboard.is_pressed('n'):
                print("\n[!] Chuan bi chup man hinh trong 0.5s...")
                time.sleep(0.5)
                
                sct = mss.mss()
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                win_title = "CHON NAMETAG NHAN VAT"
                print("[!] Keo chat quanh BUBBLE TEN nhan vat (vi du: 'ngducvii')")
                print("    (Chi keo phan chu, khong lay vung xung quanh qua nhieu)")
                print("    Nhan ENTER/SPACE de xac nhan. Nhan C de huy.")
                
                cv2.namedWindow(win_title, cv2.WINDOW_NORMAL)
                cv2.setWindowProperty(win_title, cv2.WND_PROP_TOPMOST, 1)
                
                roi = cv2.selectROI(win_title, img_bgr, fromCenter=False, showCrosshair=True)
                cv2.destroyWindow(win_title)
                for _ in range(10):
                    cv2.waitKey(1)
                
                if roi[2] > 0 and roi[3] > 0:
                    rx, ry, rw, rh = roi
                    nametag_tmpl = img_bgr[ry:ry+rh, rx:rx+rw]
                    cv2.imwrite("nametag_template.png", nametag_tmpl)
                    print(f"[OK] Da luu nametag template: {rw}x{rh} px -> 'nametag_template.png'")
                else:
                    print("[!] Da huy chup nametag.")
                time.sleep(0.5)

            elif keyboard.is_pressed('esc'):
                print("\nDang ghi nhan va thoat...")
                break
                
            time.sleep(0.01)
        except KeyboardInterrupt:
            break

    # Cap nhat va luu lai
    if game_area:
        config["game_area"] = game_area
    if watch_area:
        config["watch_area"] = watch_area
    if watch_area_shadow:
        config["watch_area_shadow"] = watch_area_shadow
    if nametag_area:
        config["nametag_area"] = nametag_area
        
    save_config(config)

if __name__ == "__main__":
    main()
