import cv2
import numpy as np

class StateFeatureExtractor:
    def __init__(self, target_size=(64, 64), hsv_bins=(8, 8, 8)):
        self.target_size = target_size
        self.hsv_bins = hsv_bins

    def extract(self, img):
        """
        Trích xuất đặc trưng kết hợp từ:
        1. Ảnh thu nhỏ (Resized image) để giữ thông tin cấu trúc/giao diện chung.
        2. Lược đồ màu sắc HSV (Color Histogram) để nhận diện các màu đặc trưng (ví dụ: dấu chấm than đỏ, màu phao câu, nút bấm).
        """
        # 1. Trích xuất đặc trưng cấu trúc (Resized BGR)
        resized = cv2.resize(img, self.target_size)
        # Chuẩn hóa giá trị pixel về khoảng [0, 1] và làm phẳng
        struct_feat = resized.astype(np.float32).flatten() / 255.0

        # 2. Trích xuất đặc trưng màu sắc (HSV Histogram)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, self.hsv_bins,
                            [0, 180, 0, 256, 0, 256])
        # Chuẩn hóa histogram
        cv2.normalize(hist, hist)
        color_feat = hist.flatten()

        # Kết hợp các vector đặc trưng lại với nhau
        combined_feat = np.concatenate([struct_feat, color_feat])
        return combined_feat
