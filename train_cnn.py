import os
import time
import copy
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms, models
from collections import Counter
import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit

# Cấu hình các thông số
DATASET_DIR = "dataset"
MODEL_FILE = "fishing_cnn.pth"
IMAGE_SIZE = (224, 224)  # ResNet18 tối ưu cho 224x224
BATCH_SIZE = 16
EPOCHS = 30
LEARNING_RATE = 0.001
VAL_SPLIT = 0.2

# === MODEL: Sử dụng ResNet18 pretrained (Transfer Learning) ===
class FishingCNN(nn.Module):
    """
    Transfer Learning với ResNet18:
    - Giữ nguyên các lớp feature extraction đã học từ ImageNet
    - Chỉ thay thế lớp fully connected cuối cùng cho 7 class
    - Hiệu quả gấp nhiều lần so với train từ đầu khi dataset nhỏ
    """
    def __init__(self, num_classes=7):
        super(FishingCNN, self).__init__()
        # Load ResNet18 pretrained trên ImageNet
        self.backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        
        # Đóng băng các lớp đầu (feature extraction) - không cần train lại
        for param in list(self.backbone.parameters())[:-20]:
            param.requires_grad = False
        
        # Thay thế lớp FC cuối cùng cho bài toán 7 class
        num_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Sequential(
            nn.Dropout(0.4),
            nn.Linear(num_features, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        return self.backbone(x)

def stratified_split(dataset, val_ratio=0.2):
    """
    Chia train/val THEO TỪNG CLASS (stratified) để đảm bảo 
    mỗi class đều có mẫu trong cả train và val.
    Quan trọng khi có class chỉ 4-7 ảnh!
    """
    targets = np.array(dataset.targets)
    
    # Với class quá ít (<3 ảnh), bỏ hết vào train
    sss = StratifiedShuffleSplit(n_splits=1, test_size=val_ratio, random_state=42)
    
    try:
        train_idx, val_idx = next(sss.split(np.zeros(len(targets)), targets))
    except ValueError:
        # Nếu stratified split thất bại (class quá ít), fallback random
        print("[!] Canh bao: Mot so class qua it anh, su dung random split.")
        indices = np.random.permutation(len(dataset))
        split = int(len(dataset) * (1 - val_ratio))
        train_idx, val_idx = indices[:split], indices[split:]
    
    return train_idx.tolist(), val_idx.tolist()

def main():
    print("==================================================")
    print("  HUAN LUYEN CNN v3 (TRANSFER LEARNING - RESNET18)")
    print("==================================================")
    
    if not os.path.exists(DATASET_DIR):
        print(f"[Loi] Khong tim thay thu muc '{DATASET_DIR}'.")
        return

    # === TRANSFORMS ===
    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomCrop(IMAGE_SIZE),
        transforms.RandomHorizontalFlip(p=0.3),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.05),
        transforms.RandomAffine(degrees=5, translate=(0.05, 0.05)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Load dataset 2 lần với transform khác nhau
    train_dataset_full = datasets.ImageFolder(root=DATASET_DIR, transform=train_transform)
    val_dataset_full = datasets.ImageFolder(root=DATASET_DIR, transform=val_transform)

    num_classes = len(train_dataset_full.classes)
    total_images = len(train_dataset_full)
    
    print(f"\n[+] Tim thay {total_images} anh thuoc {num_classes} lop:")
    for idx, class_name in enumerate(train_dataset_full.classes):
        count = train_dataset_full.targets.count(idx)
        print(f"  - Lop {idx}: {class_name} ({count} anh)")

    # === STRATIFIED SPLIT ===
    train_indices, val_indices = stratified_split(train_dataset_full, VAL_SPLIT)
    
    train_dataset = Subset(train_dataset_full, train_indices)
    val_dataset = Subset(val_dataset_full, val_indices)
    
    print(f"\n[i] Chia du lieu (Stratified): {len(train_indices)} train / {len(val_indices)} validation")
    
    # Kiểm tra phân bố class trong train/val
    train_targets = [train_dataset_full.targets[i] for i in train_indices]
    val_targets = [val_dataset_full.targets[i] for i in val_indices]
    print("[i] Phan bo trong tap Train:", dict(Counter(train_targets)))
    print("[i] Phan bo trong tap Val:  ", dict(Counter(val_targets)))

    # === CLASS WEIGHTS ===
    class_counts = Counter(train_dataset_full.targets)
    total = sum(class_counts.values())
    class_weights = {cls: total / (num_classes * count) for cls, count in class_counts.items()}
    
    print("\n[i] Trong so class:")
    for cls in sorted(class_weights.keys()):
        print(f"  - {train_dataset_full.classes[cls]}: {class_weights[cls]:.2f}")

    # Weighted sampler cho train
    train_sample_weights = [class_weights[train_dataset_full.targets[i]] for i in train_indices]
    from torch.utils.data import WeightedRandomSampler
    train_sampler = WeightedRandomSampler(train_sample_weights, len(train_indices), replacement=True)
    
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, sampler=train_sampler)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    # === MODEL ===
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n[i] Thiet bi: {device}")
    
    model = FishingCNN(num_classes=num_classes).to(device)
    
    # Đếm tham số trainable
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[i] Tham so: {trainable:,} trainable / {total_params:,} tong")
    
    weight_tensor = torch.tensor(
        [class_weights.get(i, 1.0) for i in range(num_classes)], dtype=torch.float32
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=weight_tensor)
    
    # Optimizer chỉ cho các tham số trainable
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), 
                          lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

    # === TRAINING LOOP ===
    print("\n[*] Bat dau huan luyen...")
    best_val_acc = 0.0
    best_model_state = None
    no_improve_count = 0
    EARLY_STOP_PATIENCE = 10
    start_time = time.time()

    for epoch in range(EPOCHS):
        # --- TRAIN ---
        model.train()
        running_loss, correct, total_train = 0.0, 0, 0
        
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * images.size(0)
            _, predicted = torch.max(outputs, 1)
            total_train += labels.size(0)
            correct += (predicted == labels).sum().item()

        train_loss = running_loss / total_train
        train_acc = (correct / total_train) * 100

        # --- VALIDATION ---
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * images.size(0)
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()

        val_loss = val_loss / val_total if val_total > 0 else 0
        val_acc = (val_correct / val_total) * 100 if val_total > 0 else 0
        
        scheduler.step(val_loss)
        lr = optimizer.param_groups[0]['lr']
        
        print(f" Epoch {epoch+1:02d}/{EPOCHS:02d} | "
              f"Train: {train_loss:.4f} / {train_acc:.1f}% | "
              f"Val: {val_loss:.4f} / {val_acc:.1f}% | LR: {lr:.6f}")

        # Lưu model tốt nhất
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_state = copy.deepcopy(model.state_dict())
            no_improve_count = 0
            print(f"   >>> Model tot nhat! Val Acc: {val_acc:.1f}%")
        else:
            no_improve_count += 1
            
        # Early stopping
        if no_improve_count >= EARLY_STOP_PATIENCE:
            print(f"\n[!] Early stopping: {EARLY_STOP_PATIENCE} epoch khong cai thien.")
            break

    duration = time.time() - start_time
    
    # Lưu model tốt nhất
    if best_model_state:
        torch.save(best_model_state, MODEL_FILE)
    
    print(f"\n{'='*50}")
    print(f"[+] Hoan tat trong {duration:.1f}s")
    print(f"[+] Val Accuracy tot nhat: {best_val_acc:.1f}%")
    print(f"[+] Model luu tai: '{MODEL_FILE}'")

if __name__ == "__main__":
    main()
