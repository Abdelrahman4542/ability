"""Arabic/English printed-text OCR using EasyOCR pretrained models."""
from pathlib import Path


class OCRService:
    def __init__(self, languages=("ar", "en"), gpu=None):
        self.languages = list(languages)
        self.gpu = gpu
        self.reader = None
        self.error = None

    def _load(self):
        if self.reader is not None:
            return
        try:
            import torch
            import easyocr
            use_gpu = torch.cuda.is_available() if self.gpu is None else bool(self.gpu)
            # EasyOCR downloads its pretrained language weights on first use.
            self.reader = easyocr.Reader(self.languages, gpu=use_gpu, verbose=False)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(
                "EasyOCR could not initialize. Check internet access for its first model download "
                "and verify the installed PyTorch/EasyOCR versions. " + self.error
            ) from exc

    def read(self, image_path_or_array):
        self._load()
        if isinstance(image_path_or_array, (str, Path)):
            image = str(image_path_or_array)
        else:
            image = image_path_or_array
        results = self.reader.readtext(image, detail=1, paragraph=False)
        lines = []
        for _box, text, confidence in results:
            clean = str(text).strip()
            if clean:
                lines.append({"text": clean, "confidence": float(confidence)})
        return lines
