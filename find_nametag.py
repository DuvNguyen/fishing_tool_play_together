import cv2
import numpy as np
import mss
import time
import keyboard
import tkinter as tk

class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "black")
        
        # Click chuột xuyên qua overlay
        try:
            self.root.wm_attributes("-disabled", True)
        except:
            pass

        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+0+0")
        
        self.canvas = tk.Canvas(self.root, width=w, height=h, bg="black", highlightthickness=0)
        self.canvas.pack()
        
    def draw_boxes(self, nametag_box, scan_box):
        self.canvas.delete("all")
        if nametag_box:
            x, y, w, h = nametag_box
            # Khung xanh lá quanh chữ tên nhân vật
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#00FF00", width=2)
            # Viết chữ debug
            self.canvas.create_text(x, y-10, text="Name Detected", fill="#00FF00", anchor="w")
        if scan_box:
            x, y, w, h = scan_box
            # Khung xanh dương quét chấm than
            self.canvas.create_rectangle(x, y, x+w, y+h, outline="#0000FF", width=2)
            
    def update_window(self):
        self.root.update()

def main():
    print("==================================================")
    print("      TEST DYNAMIC NAMETAG DETECTOR (HSV MASK)")
    print("==================================================")
    print("Huong dan:")
    print(" - Tool se tu dong tim kiem chu mau XANH LA NEON (ten ban) tren man hinh.")
    print(" - KHONG can anh nametag_template.png.")
    print(" - Nhấn 'R' để bắt đầu.")
    print(" - Giữ 'Q' để thoát.")
    print("==================================================")

    sct = mss.mss()
    monitor = sct.monitors[1] # Toàn màn hình
    screen_w = monitor["width"]
    screen_h = monitor["height"]

    overlay = Overlay()

    while True:
        if keyboard.is_pressed('r'):
            break
        overlay.update_window()
        time.sleep(0.01)

    print("[+] Da bat dau quet tim ten...")

    try:
        while True:
            overlay.update_window()
            if keyboard.is_pressed('q'):
                print("[-] Dang thoat...")
                break

            # Chụp màn hình
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Chuyển sang HSV để lọc màu xanh lá của tên
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            
            # Dải màu xanh lá cây neon của tên (điều chỉnh nếu cần)
            lower_green = np.array([35, 100, 100])
            upper_green = np.array([85, 255, 255])
            
            mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Tìm các vùng màu xanh (contours)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            detected_nametag = None
            
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                
                # Lọc các nhiễu nhỏ: Tên nhân vật thường có kích thước tối thiểu và tỷ lệ dài/rộng phù hợp
                # Thường chữ tên sẽ dài (w > h)
                aspect_ratio = w / float(h)
                
                # Bạn có thể điều chỉnh các con số này nếu tên quá dài hoặc ngắn
                if w > 30 and h > 8 and aspect_ratio > 1.5 and aspect_ratio < 10.0:
                    # Để tránh nhận diện nhầm các vật thể màu xanh khác, ta ưu tiên vùng nằm ở nửa dưới màn hình (thường là nhân vật đứng)
                    # Hoặc chỉ đơn giản là lấy vùng phù hợp nhất gần tâm màn hình
                    dist_to_center = abs(x + w/2 - screen_w/2) + abs(y + h/2 - screen_h/2)
                    
                    if detected_nametag is None or dist_to_center < detected_nametag["dist"]:
                        detected_nametag = {
                            "box": (x, y, w, h),
                            "dist": dist_to_center
                        }

            if detected_nametag:
                tx, ty, tw, th = detected_nametag["box"]
                
                # Tính toán vùng quét chấm than (Blue Box) dựa trên kích thước tên (Green Box)
                # Giúp tự động phóng to/thu nhỏ vùng quét khi bạn zoom camera xa/gần
                scan_h_top = int(th * 5.5)
                scan_h_bottom = int(th * 1.5)
                scan_y_start = max(0, ty - scan_h_top)
                scan_y_end = max(0, ty - scan_h_bottom)
                
                margin = int(tw * 0.3)
                scan_x_start = max(0, tx - margin)
                scan_x_end = min(screen_w, tx + tw + margin)
                
                nametag_box = (tx, ty, tw, th)
                scan_box = (scan_x_start, scan_y_start, scan_x_end - scan_x_start, scan_y_end - scan_y_start)
                
                # Vẽ lên màn hình game
                overlay.draw_boxes(nametag_box, scan_box)
            else:
                # Không tìm thấy tên thì xóa khung
                overlay.draw_boxes(None, None)

            time.sleep(0.02) # Giới hạn khoảng 50 FPS để đỡ ngốn CPU

    except Exception as e:
        print(f"[Loi] {e}")

if __name__ == "__main__":
    main()
