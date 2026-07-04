# ============================================================
#  FISHING BOT CNN - GOOGLE COLAB TRAINING NOTEBOOK
#  Copy từng cell vào Colab để chạy
# ============================================================

# ============ CELL 1: Kiểm tra dataset.zip ============
# Upload file dataset.zip lên Colab qua Files panel (kéo thả bên trái)
# Sau đó chạy cell này để kiểm tra
import os
if os.path.exists('dataset.zip'):
    size_mb = os.path.getsize('dataset.zip') / (1024 * 1024)
    print(f"[OK] Da tim thay dataset.zip ({size_mb:.1f} MB)")
else:
    print("[LOI] Khong tim thay dataset.zip!")
    print("Hay upload file dataset.zip vao Colab truoc (keo tha vao Files panel ben trai)")

# ============ CELL 2: Giải nén dataset ============
import zipfile
with zipfile.ZipFile('dataset.zip', 'r') as zip_ref:
    zip_ref.extractall('.')

# Kiểm tra cấu trúc
import os
for folder in sorted(os.listdir('dataset')):
    count = len(os.listdir(os.path.join('dataset', folder)))
    print(f"  {folder}: {count} ảnh")

# ============ CELL 3: Training (CHÍNH) ============
import os
import time
import copy
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
from torchvision import datasets, transforms, models
from collections import Counter
import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit

# === CẤU HÌNH ===
DATASET_DIR = "dataset"
MODEL_FILE = "fishing_cnn.pth"
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32       # Colab GPU mạnh hơn -> batch lớn hơn
EPOCHS = 50
LEARNING_RATE = 0.001
VAL_SPLIT = 0.2

# === MODEL: ResNet18 Transfer Learning ===
class FishingCNN(nn.Module):
    def __init__(self, num_classes=7):
        super(FishingCNN, self).__init__()
        self.backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        
        # Đóng băng các lớp đầu
        for param in list(self.backbone.parameters())[:-20]:
            param.requires_grad = False
        
        # Thay FC cuối
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

# === LOAD DATA ===
train_dataset_full = datasets.ImageFolder(root=DATASET_DIR, transform=train_transform)
val_dataset_full = datasets.ImageFolder(root=DATASET_DIR, transform=val_transform)

num_classes = len(train_dataset_full.classes)
total_images = len(train_dataset_full)

print(f"\n[+] {total_images} ảnh, {num_classes} class:")
for idx, name in enumerate(train_dataset_full.classes):
    count = train_dataset_full.targets.count(idx)
    print(f"  - {name}: {count}")

# === STRATIFIED SPLIT ===
targets = np.array(train_dataset_full.targets)
sss = StratifiedShuffleSplit(n_splits=1, test_size=VAL_SPLIT, random_state=42)
try:
    train_idx, val_idx = next(sss.split(np.zeros(len(targets)), targets))
except ValueError:
    indices = np.random.permutation(len(train_dataset_full))
    split = int(len(train_dataset_full) * (1 - VAL_SPLIT))
    train_idx, val_idx = indices[:split], indices[split:]

train_dataset = Subset(train_dataset_full, train_idx.tolist())
val_dataset = Subset(val_dataset_full, val_idx.tolist())

print(f"\n[i] Split: {len(train_idx)} train / {len(val_idx)} val")

# === CLASS WEIGHTS ===
class_counts = Counter(train_dataset_full.targets)
total = sum(class_counts.values())
class_weights = {cls: total / (num_classes * count) for cls, count in class_counts.items()}

print("\n[i] Class weights:")
for cls in sorted(class_weights.keys()):
    print(f"  - {train_dataset_full.classes[cls]}: {class_weights[cls]:.2f}")

# Weighted sampler
train_sample_weights = [class_weights[train_dataset_full.targets[i]] for i in train_idx]
train_sampler = WeightedRandomSampler(train_sample_weights, len(train_idx), replacement=True)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, sampler=train_sampler)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

# === MODEL + OPTIMIZER ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\n[i] Device: {device}")

model = FishingCNN(num_classes=num_classes).to(device)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"[i] Trainable params: {trainable:,}")

weight_tensor = torch.tensor(
    [class_weights.get(i, 1.0) for i in range(num_classes)], dtype=torch.float32
).to(device)
criterion = nn.CrossEntropyLoss(weight=weight_tensor)
optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),
                      lr=LEARNING_RATE, weight_decay=1e-4)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

# === TRAINING ===
print("\n[*] Bắt đầu huấn luyện trên GPU...")
best_val_acc = 0.0
best_model_state = None
no_improve = 0
PATIENCE = 10
start = time.time()

for epoch in range(EPOCHS):
    # Train
    model.train()
    r_loss, correct, total_t = 0.0, 0, 0
    for imgs, labels in train_loader:
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        out = model(imgs)
        loss = criterion(out, labels)
        loss.backward()
        optimizer.step()
        r_loss += loss.item() * imgs.size(0)
        _, pred = torch.max(out, 1)
        total_t += labels.size(0)
        correct += (pred == labels).sum().item()
    t_loss = r_loss / total_t
    t_acc = correct / total_t * 100

    # Val
    model.eval()
    v_loss, v_correct, v_total = 0.0, 0, 0
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            out = model(imgs)
            loss = criterion(out, labels)
            v_loss += loss.item() * imgs.size(0)
            _, pred = torch.max(out, 1)
            v_total += labels.size(0)
            v_correct += (pred == labels).sum().item()
    v_loss = v_loss / v_total if v_total > 0 else 0
    v_acc = v_correct / v_total * 100 if v_total > 0 else 0
    
    scheduler.step(v_loss)
    lr = optimizer.param_groups[0]['lr']
    
    mark = ""
    if v_acc > best_val_acc:
        best_val_acc = v_acc
        best_model_state = copy.deepcopy(model.state_dict())
        no_improve = 0
        mark = " ★ BEST"
    else:
        no_improve += 1
    
    print(f"Epoch {epoch+1:02d}/{EPOCHS} | "
          f"Train: {t_loss:.4f} / {t_acc:.1f}% | "
          f"Val: {v_loss:.4f} / {v_acc:.1f}% | LR: {lr:.6f}{mark}")
    
    if no_improve >= PATIENCE:
        print(f"\n[!] Early stopping sau {PATIENCE} epoch không cải thiện.")
        break

duration = time.time() - start
if best_model_state:
    torch.save(best_model_state, MODEL_FILE)

print(f"\n{'='*50}")
print(f"[+] Xong trong {duration:.1f}s")
print(f"[+] Best Val Accuracy: {best_val_acc:.1f}%")
print(f"[+] Model saved: '{MODEL_FILE}'")

# ============ CELL 4: Tải model về máy ============
from google.colab import files
files.download('fishing_cnn.pth')
# Sau khi tải về, copy file fishing_cnn.pth vào thư mục fishing_tool trên máy
