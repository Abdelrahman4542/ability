# AbilityBridge AI

Windows desktop accessibility application built with Python and PySide6. This release includes Arabic sign recognition, Arabic text building, live object detection with Arabic narration, OCR for Arabic/English printed text, and shared text-to-speech.

## Current modules

### 1. Arabic Sign Recognition + Word Builder
- Uses the supplied **ArASL2018 54,049-image dataset**, with 32 dataset classes.
- CNN classifies a static sign image; MediaPipe tracks one hand in the live camera.
- The UI shows the current candidate and confidence. A letter/sign must remain stable before it can be added.
- **Add prediction** appends the recognized Arabic output; **Space**, **Backspace**, and **Clear** edit the text; **Read built text aloud** speaks the completed word/sentence.
- The 32 dataset labels map to Arabic outputs. Four labels represent standard signs/tokens rather than one single character: `al` → `ال`, `la` → `لا`, `toot` → `ة`, and `ya` → `ئ`. `yaa` maps to `ي`.
- The dataset is static, single-hand image classification. It is not a full dynamic sign-language sentence translator.

### 2. Vision Assistant
- Start Camera begins repeated YOLO11n object detection automatically.
- Detected objects are shown with confidence values and translated to Arabic where a known label mapping exists.
- Arabic voice narration starts automatically when the set of recognized object types changes; it avoids repeating an unchanged scene every frame.
- Stop Camera stops the camera. The Read Results Aloud button remains available for manual replay.
- YOLO11n is trained on common COCO categories and cannot recognize every possible object.

### 3. OCR Assistant
- Extracts printed Arabic and English text from an uploaded image or a camera capture using EasyOCR pretrained weights.
- Displays extracted text and confidence, then sends the extracted text to the shared TTS service when Read is pressed.
- No OCR training dataset is required. EasyOCR downloads its pretrained language weights on first use, so allow internet access for that first OCR run.
- This MVP focuses on printed text; handwritten Arabic recognition is not guaranteed.

### 4. Text-to-Speech
- Sign, Vision, and OCR use one shared TTS service.
- On Windows, the application uses Windows System.Speech and prefers an installed Arabic voice. Install an Arabic Windows speech voice for better Arabic pronunciation.

## Project structure

```text
AbilityBridge_AI/
├── app/
│   ├── main_window.py
│   ├── pages/                 # Dashboard, Sign, Vision, OCR, Settings, About
│   ├── services/              # CNN/MediaPipe, YOLO, OCR, TTS, text builder
│   └── widgets/
├── datasets/
│   └── sign_language/
│       └── ArASL_Database_54K_Final/   # 32 class folders, 54,049 images
├── models/
│   ├── cnn_baseline/          # Current checkpoint and training reports
│   ├── mediapipe/             # Hand landmark task file
│   └── yolo11n.pt
├── scripts/check_project.py
├── tests/test_core_services.py
├── train_cnn.py
├── train_cnn.bat
├── requirements.txt
├── setup_windows.bat
└── run_app.bat
```

## Installation (Windows 10/11)

1. Extract the entire ZIP to a writable folder.
2. Install **Python 3.12 x64** and enable the Python Launcher.
3. Run `setup_windows.bat` and wait for all dependencies to install.
4. Run `train_cnn.bat` once to train the new 32-class CNN from the included 54K dataset. This may take a while; use the NVIDIA GPU if PyTorch detects it.
5. When training completes successfully, run `run_app.bat`.

The previous 28-class CNN checkpoint is retained as a backup until the new training run passes its held-out test evaluation. The updated app intentionally refuses to load that old checkpoint as if it were a 32-class model. Do not skip step 4 if you want the 32-class sign module to work.

## Training details

- The training script reads `datasets/sign_language/ArASL_Database_54K_Final` directly.
- It checks for all 32 expected class folders and makes a reproducible, stratified 70% / 15% / 15% train/validation/test split.
- It warm-starts compatible CNN layers from the previous 28-class checkpoint, while replacing the final classifier layer for 32 outputs.
- Training writes the candidate checkpoint, then evaluates it on the held-out test set. Only after successful evaluation does it replace `models/cnn_baseline/best_cnn_model.pth`.
- The dataset folders do not contain signer IDs, so the random image split is not signer-independent. Also, the webcam hand crop is only an approximation of the centered ArASL training image framing. Real webcam accuracy can be lower than the reported test accuracy. Test with multiple people, lighting conditions, distances, and camera positions; if needed, collect a small set of webcam examples for fine-tuning.
- Dataset source: Latif et al., *ArASL: Arabic Alphabets Sign Language Dataset*, ArASL2018, 54,049 images / 32 classes, CC BY 4.0. Cite the dataset if redistributing or publishing results.

## Run diagnostics and tests

```bat
.venv\Scripts\python.exe scripts\check_project.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Practical notes

- Sign Recognition currently targets one static hand pose at a time. Keep the full hand in view and hold the sign steady until the result becomes stable.
- Add Prediction only appends a stable result. It does not automatically add every frame, preventing repeated letters while the hand is held still.
- The dataset includes 32 labels but some are multi-character signs/tokens. The text builder accepts these outputs; the class labels are not all one Unicode character.
- Vision narration is triggered by changes in recognized object categories, not every frame. Manual replay is available.
- OCR first-run model download requires internet access. No OCR dataset needs to be downloaded.
- For Arabic TTS, the computer must have an Arabic Windows voice installed. TTS availability does not guarantee Arabic pronunciation if the voice is missing.
- Large model/data files are included in this project archive; do not commit the `.venv` folder or generated Python caches to Git.
