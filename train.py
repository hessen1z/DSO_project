"""
YOLOv8 Training Script for Drakensang Bot
==========================================
- Images in: dataset/
- Labels in: source/
- Merges both into proper YOLO train/val structure
- Trains YOLOv8n on GPU (CUDA) if available
"""

import os
import shutil
import random
import yaml
from pathlib import Path

# =============================================
# CONFIG
# =============================================
IMAGES_DIR = Path("dataset")          # صور PNG هنا
LABELS_DIR = Path("source")           # ملفات TXT (labels) هنا
OUTPUT_DIR = Path("detection/models") # مكان حفظ best.pt
YOLO_DATA  = Path("dataset_yolo")     # فولدر مؤقت للتدريب
TRAIN_RATIO = 0.8
EPOCHS = 100
BATCH_SIZE = 8
IMG_SIZE = 640

# أسماء الكلاسات كما عملتها في labelImg
CLASSES = [
    "enemy", "elite", "boss", "loot", "portal",
    "npc", "dead_screen", "hp_bar", "inventory_full"
]


def build_yolo_structure():
    """يجمع الصور + الـ Labels ويقسمهم train/val"""
    print("📂 Building YOLO dataset structure...")

    # احذف القديم لو موجود
    if YOLO_DATA.exists():
        shutil.rmtree(YOLO_DATA)

    for split in ["train", "val"]:
        (YOLO_DATA / split / "images").mkdir(parents=True)
        (YOLO_DATA / split / "labels").mkdir(parents=True)

    # اجمع كل الصور اللي عندها label
    pairs = []
    for img_path in IMAGES_DIR.glob("*.png"):
        label_path = LABELS_DIR / (img_path.stem + ".txt")
        if label_path.exists():
            pairs.append((img_path, label_path))

    print(f"✅ Found {len(pairs)} labeled image pairs")

    if len(pairs) == 0:
        print("❌ No matched image+label pairs found!")
        print(f"   Images dir: {IMAGES_DIR.resolve()}")
        print(f"   Labels dir: {LABELS_DIR.resolve()}")
        return False

    # Shuffle + split
    random.seed(42)
    random.shuffle(pairs)
    split_idx = int(len(pairs) * TRAIN_RATIO)
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]

    print(f"   Train: {len(train_pairs)} | Val: {len(val_pairs)}")

    # Copy files
    for img, lbl in train_pairs:
        shutil.copy(img, YOLO_DATA / "train" / "images" / img.name)
        shutil.copy(lbl, YOLO_DATA / "train" / "labels" / lbl.name)

    for img, lbl in val_pairs:
        shutil.copy(img, YOLO_DATA / "val" / "images" / img.name)
        shutil.copy(lbl, YOLO_DATA / "val" / "labels" / lbl.name)

    # Write data.yaml
    data_yaml = {
        "path": str(YOLO_DATA.resolve()),
        "train": "train/images",
        "val":   "val/images",
        "nc":    len(CLASSES),
        "names": CLASSES
    }

    yaml_path = YOLO_DATA / "data.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data_yaml, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ data.yaml saved: {yaml_path}")
    return True


def train():
    """Start YOLOv8 training"""
    import torch
    from ultralytics import YOLO

    # Check GPU
    device = "0" if torch.cuda.is_available() else "cpu"
    print("\n" + "=" * 55)
    if device == "0":
        print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
        print(f"🔥 Training on: CUDA (GPU)")
    else:
        print("⚠️  CUDA not available — training on CPU (slower)")
    print("=" * 55 + "\n")

    # Build dataset structure
    if not build_yolo_structure():
        return

    # Load YOLOv8 nano base model
    print("📥 Loading YOLOv8n base model...")
    model = YOLO("yolov8n.pt")

    # Train!
    print(f"🚀 Starting training: {EPOCHS} epochs, batch={BATCH_SIZE}, img={IMG_SIZE}...")
    results = model.train(
        data=str((YOLO_DATA / "data.yaml").resolve()),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device=device,
        project="drakensang_yolo",
        name="run",
        exist_ok=True,
        patience=20,        # Early stopping
        save=True,
        plots=True,
        verbose=True,
        workers=2,          # Optimize dataloader
        cache=True          # Cache images in RAM for speed
    )

    # Copy best weights to detection/models/
    best_weights = Path("runs/detect/drakensang_yolo/run/weights/best.pt")
    if best_weights.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUTPUT_DIR / "best.pt"
        shutil.copy(best_weights, dest)
        print(f"\n{'='*55}")
        print(f"🏆 SUCCESS! Model saved to: {dest}")
        print(f"{'='*55}")
        print("\n✅ Now update config/settings.json:")
        print('   "model_path": "detection/models/best.pt"')
    else:
        print("⚠️ Training done but best.pt not found.")


if __name__ == "__main__":
    train()
