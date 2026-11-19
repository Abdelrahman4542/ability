"""Train a 32-class ArASL CNN from the original class-folder dataset.

Expected data layout:
  datasets/sign_language/ArASL_Database_54K_Final/<class_name>/*.jpg
The script makes a reproducible stratified 70/15/15 split in memory and writes
metrics/checkpoints to models/cnn_baseline. The source dataset is not modified.
"""
from pathlib import Path
from collections import Counter
import copy
import json
import os
import random

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "models" / "cnn_baseline"
IMAGE_SIZE = 64
BATCH_SIZE = int(os.environ.get("ARASL_BATCH_SIZE", "32"))
EPOCHS = int(os.environ.get("ARASL_EPOCHS", "30"))
LEARNING_RATE = 0.001
PATIENCE = 7
SEED = 42
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def find_dataset_dir():
    configured = os.environ.get("ARASL_DATA_DIR", "").strip().strip('"')
    candidates = [Path(configured).expanduser()] if configured else []
    candidates += [
        BASE_DIR / "datasets" / "sign_language" / "ArASL_Database_54K_Final",
        BASE_DIR / "ArASL_Database_54K_Final",
    ]
    for candidate in candidates:
        if candidate.is_dir() and any(x.is_dir() for x in candidate.iterdir()):
            return candidate
    raise FileNotFoundError(
        "ArASL class folders were not found. Extract ArASL_Database_54K_Final.zip "
        "to datasets/sign_language/ArASL_Database_54K_Final, or set ARASL_DATA_DIR."
    )


class SignLanguageCNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(), nn.Linear(256, 128), nn.ReLU(inplace=True),
            nn.Dropout(0.4), nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
        torch.backends.cudnn.benchmark = True

    data_dir = find_dataset_dir()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Dataset: {data_dir}\nDevice: {DEVICE}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    base_dataset = datasets.ImageFolder(data_dir)
    expected = {
        "ain", "al", "aleff", "bb", "dal", "dha", "dhad", "fa", "gaaf", "ghain",
        "ha", "haa", "jeem", "kaaf", "khaa", "la", "laam", "meem", "nun", "ra",
        "saad", "seen", "sheen", "ta", "taa", "thaa", "thal", "toot", "waw", "ya", "yaa", "zay"
    }
    if set(base_dataset.classes) != expected or len(base_dataset.classes) != 32:
        raise ValueError(f"Expected exactly 32 ArASL classes. Found: {base_dataset.classes}")

    targets = np.asarray(base_dataset.targets)
    indices = np.arange(len(targets))
    train_idx, remainder_idx = train_test_split(
        indices, test_size=0.30, random_state=SEED, stratify=targets
    )
    val_idx, test_idx = train_test_split(
        remainder_idx, test_size=0.50, random_state=SEED, stratify=targets[remainder_idx]
    )
    print(f"Images: {len(base_dataset)} | train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")
    print("Classes:", ", ".join(base_dataset.classes))

    train_transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.72, 1.0), ratio=(0.88, 1.12)),
        transforms.RandomAffine(degrees=10, translate=(0.07, 0.07), scale=(0.90, 1.10), shear=4),
        transforms.RandomPerspective(distortion_scale=0.10, p=0.15),
        transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,)),
        transforms.RandomErasing(p=0.10, scale=(0.01, 0.06), ratio=(0.5, 2.0), value=0),
    ])
    eval_transform = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,)),
    ])
    train_data = datasets.ImageFolder(data_dir, transform=train_transform)
    eval_data = datasets.ImageFolder(data_dir, transform=eval_transform)
    train_loader = DataLoader(Subset(train_data, train_idx), batch_size=BATCH_SIZE,
                              shuffle=True, num_workers=0, pin_memory=torch.cuda.is_available())
    val_loader = DataLoader(Subset(eval_data, val_idx), batch_size=BATCH_SIZE,
                            shuffle=False, num_workers=0, pin_memory=torch.cuda.is_available())
    test_loader = DataLoader(Subset(eval_data, test_idx), batch_size=BATCH_SIZE,
                             shuffle=False, num_workers=0, pin_memory=torch.cuda.is_available())

    model = SignLanguageCNN(len(base_dataset.classes)).to(DEVICE)
    # Warm-start convolutional features from the previous 28-class model when available.
    old_checkpoint_path = OUTPUT_DIR / "best_cnn_model.pth"
    if old_checkpoint_path.is_file():
        try:
            old_bundle = torch.load(old_checkpoint_path, map_location="cpu", weights_only=True)
            old_state = old_bundle.get("model_state_dict", {})
            current_state = model.state_dict()
            compatible = {k: v for k, v in old_state.items()
                          if k in current_state and current_state[k].shape == v.shape}
            model.load_state_dict(compatible, strict=False)
            print(f"Warm-started {len(compatible)} parameter tensors from previous CNN checkpoint.")
        except Exception as exc:
            print(f"Warm-start skipped: {type(exc).__name__}: {exc}")
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=2)

    def run_epoch(loader, training=False):
        model.train(training)
        total_loss = correct = total = 0
        for images, labels in loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.set_grad_enabled(training):
                logits = model(images)
                loss = criterion(logits, labels)
                if training:
                    loss.backward()
                    optimizer.step()
            total_loss += loss.item() * images.size(0)
            correct += (logits.argmax(1) == labels).sum().item()
            total += labels.size(0)
        return total_loss / max(total, 1), correct / max(total, 1)

    best_val = 0.0
    best_epoch = 0
    patience = 0
    history = []
    candidate_path = OUTPUT_DIR / "candidate_cnn_model.pth"
    candidate_path.unlink(missing_ok=True)
    for epoch in range(EPOCHS):
        train_loss, train_acc = run_epoch(train_loader, True)
        val_loss, val_acc = run_epoch(val_loader, False)
        scheduler.step(val_acc)
        history.append({"epoch": epoch + 1, "train_loss": train_loss, "train_accuracy": train_acc,
                        "val_loss": val_loss, "val_accuracy": val_acc,
                        "learning_rate": optimizer.param_groups[0]["lr"]})
        print(f"Epoch {epoch+1:02d}/{EPOCHS} | train {train_acc:.4f} | val {val_acc:.4f} | loss {val_loss:.4f}")
        if val_acc > best_val:
            best_val, best_epoch, patience = val_acc, epoch + 1, 0
            torch.save({
                "model_state_dict": copy.deepcopy(model.state_dict()),
                "class_names": base_dataset.classes,
                "class_to_idx": base_dataset.class_to_idx,
                "image_size": IMAGE_SIZE,
                "num_classes": len(base_dataset.classes),
                "best_epoch": best_epoch,
                "best_val_accuracy": best_val,
                "preprocessing": "grayscale_64_center_resize_with_train_augmentation",
                "dataset": "ArASL2018_54049_32_classes",
            }, candidate_path)
        else:
            patience += 1
        if patience >= PATIENCE:
            print("Early stopping.")
            break

    pd.DataFrame(history).to_csv(OUTPUT_DIR / "training_history.csv", index=False)
    checkpoint = torch.load(candidate_path, map_location=DEVICE, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    predictions, truths = [], []
    with torch.inference_mode():
        for images, labels in test_loader:
            logits = model(images.to(DEVICE))
            predictions.extend(logits.argmax(1).cpu().numpy().tolist())
            truths.extend(labels.numpy().tolist())
    report = classification_report(truths, predictions, labels=list(range(32)),
                                   target_names=base_dataset.classes, output_dict=True, zero_division=0)
    pd.DataFrame(report).transpose().to_csv(OUTPUT_DIR / "classification_report.csv")
    np.savetxt(OUTPUT_DIR / "confusion_matrix.csv", confusion_matrix(truths, predictions), delimiter=",", fmt="%d")
    test_acc = float(np.mean(np.asarray(predictions) == np.asarray(truths)))
    results = {
        "model": "CNN Baseline - ArASL 32 classes", "device": str(DEVICE),
        "image_size": IMAGE_SIZE, "batch_size": BATCH_SIZE, "epochs_completed": len(history),
        "best_epoch": best_epoch, "best_validation_accuracy": best_val, "test_accuracy": test_acc,
        "num_classes": 32, "total_images": len(base_dataset),
        "train_images": len(train_idx), "validation_images": len(val_idx), "test_images": len(test_idx),
        "split_note": "Stratified random image split; not signer-independent because signer IDs are not supplied in the class folders."
    }
    (OUTPUT_DIR / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    # Promote only after successful held-out evaluation.
    torch.save(checkpoint, OUTPUT_DIR / "best_cnn_model.pth")
    print(json.dumps(results, indent=2))
    print("Production checkpoint updated:", OUTPUT_DIR / "best_cnn_model.pth")


if __name__ == "__main__":
    main()
