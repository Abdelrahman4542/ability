"""Unicode-safe text buffer for Arabic letters and multi-character ArASL signs."""

class TextBuilderService:
    def __init__(self):
        self._text = ""

    @property
    def text(self):
        return self._text

    def add_text(self, value: str) -> str:
        token = str(value).strip()
        if not token:
            raise ValueError("A recognized Arabic sign is required.")
        self._text += token
        return self._text

    def add_letter(self, letter: str) -> str:
        value = str(letter).strip()
        if len(value) != 1:
            raise ValueError("A single Arabic character is required.")
        return self.add_text(value)

    def add_space(self) -> str:
        if self._text and not self._text.endswith(" "):
            self._text += " "
        return self._text

    def backspace(self) -> str:
        self._text = self._text[:-1]
        return self._text

    def clear(self) -> str:
        self._text = ""
        return self._text
