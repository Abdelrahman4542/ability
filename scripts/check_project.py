"""AbilityBridge AI release diagnostics for the 32-class ArASL build."""
from pathlib import Path
import argparse
import ast
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "datasets" / "sign_language" / "ArASL_Database_54K_Final"
CLASSES = {
    "ain", "al", "aleff", "bb", "dal", "dha", "dhad", "fa", "gaaf", "ghain",
    "ha", "haa", "jeem", "kaaf", "khaa", "la", "laam", "meem", "nun", "ra",
    "saad", "seen", "sheen", "ta", "taa", "thaa", "thal", "toot", "waw", "ya", "yaa", "zay"
}
REQUIRED = [
    "main.py", "requirements.txt", "train_cnn.py", "train_cnn.bat", "app/main_window.py",
    "app/pages/sign_page.py", "app/pages/vision_page.py", "app/pages/ocr_page.py",
    "app/services/sign_service.py", "app/services/vision_service.py",
    "app/services/ocr_service.py", "app/services/tts_service.py",
    "models/mediapipe/hand_landmarker.task", "yolo11n.pt",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-only", action="store_true")
    args = parser.parse_args()
    failures = []
    print("=" * 64 + "\nABILITYBRIDGE AI · RELEASE DIAGNOSTICS\n" + "=" * 64)

    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    if missing:
        failures.append("Missing required files: " + ", ".join(missing))
    else:
        print("PASS required project files")

    pyfiles = list((ROOT / "app").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")) + list(ROOT.glob("*.py"))
    try:
        for file in pyfiles:
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        print(f"PASS Python syntax: {len(pyfiles)} files")
    except Exception as exc:
        failures.append(f"Python syntax: {type(exc).__name__}: {exc}")

    if DATA.is_dir():
        found_classes = {p.name for p in DATA.iterdir() if p.is_dir()}
        image_count = sum(1 for p in DATA.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        print(f"ArASL dataset: {image_count:,} images · {len(found_classes)} classes")
        if found_classes != CLASSES or image_count != 54049:
            failures.append("ArASL dataset class folders/count do not match the expected 32-class 54,049-image release")
        else:
            print("PASS ArASL 54K dataset structure")
    else:
        failures.append(f"ArASL dataset folder missing: {DATA}")

    try:
        from app.services.sign_service import ARABIC_LABELS
        if set(ARABIC_LABELS) != CLASSES:
            raise ValueError("Arabic label mapping does not match the 32 dataset classes")
        print("PASS 32-class Arabic output mapping")
    except Exception as exc:
        failures.append(f"Sign label mapping: {type(exc).__name__}: {exc}")

    checkpoint = ROOT / "models" / "cnn_baseline" / "best_cnn_model.pth"
    if checkpoint.exists():
        print("NOTE existing CNN checkpoint is retained as a backup; run train_cnn.bat to generate the 32-class model.")
    else:
        print("NOTE train the CNN using train_cnn.bat after setup.")

    try:
        import unittest
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            failures.append("Unit tests failed")
        else:
            print("PASS core unit tests")
    except Exception as exc:
        failures.append(f"Unit tests: {type(exc).__name__}: {exc}")

    if not args.core_only:
        for module in ("PySide6", "cv2", "mediapipe", "ultralytics", "torch", "torchvision", "sklearn", "pandas", "matplotlib", "PIL", "easyocr"):
            try:
                importlib.import_module(module)
                print("PASS dependency", module)
            except Exception as exc:
                failures.append(f"Dependency {module}: {type(exc).__name__}: {exc}")
        try:
            for module in ("app.pages.sign_page", "app.pages.vision_page", "app.pages.ocr_page", "app.main_window"):
                importlib.import_module(module)
            print("PASS desktop UI module imports")
        except Exception as exc:
            failures.append(f"Desktop UI imports: {type(exc).__name__}: {exc}")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(" -", failure)
        return 1
    print("\nALL CHECKS PASSED. Train the 32-class CNN before using live sign recognition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
