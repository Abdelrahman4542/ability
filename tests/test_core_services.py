import unittest
import numpy as np

from app.services.sign_service import preprocess_image, ARABIC_LABELS
from app.services.text_builder_service import TextBuilderService


class SignPreprocessingTests(unittest.TestCase):
    def test_preprocessing_shape_and_range(self):
        image = np.zeros((120, 80, 3), dtype=np.uint8)
        image[20:100, 20:60] = 255
        tensor = preprocess_image(image)
        self.assertEqual(tensor.shape, (1, 1, 64, 64))
        self.assertTrue(np.isfinite(tensor).all())
        self.assertGreaterEqual(float(tensor.min()), -1.0)
        self.assertLessEqual(float(tensor.max()), 1.0)

    def test_all_32_arasl_classes_are_mapped(self):
        self.assertEqual(len(ARABIC_LABELS), 32)
        self.assertEqual(ARABIC_LABELS["al"], "ال")
        self.assertEqual(ARABIC_LABELS["la"], "لا")
        self.assertEqual(ARABIC_LABELS["toot"], "ة")
        self.assertEqual(ARABIC_LABELS["ya"], "ئ")
        self.assertEqual(ARABIC_LABELS["yaa"], "ي")


class TextBuilderTests(unittest.TestCase):
    def test_build_arabic_word_and_sentence(self):
        builder = TextBuilderService()
        for letter in "سلام":
            builder.add_letter(letter)
        builder.add_space()
        builder.add_letter("ب")
        self.assertEqual(builder.text, "سلام ب")

    def test_multi_character_sign_tokens(self):
        builder = TextBuilderService()
        builder.add_text("ال")
        builder.add_text("لا")
        self.assertEqual(builder.text, "اللا")

    def test_space_backspace_clear(self):
        builder = TextBuilderService()
        builder.add_letter("م")
        builder.add_space()
        builder.add_space()
        self.assertEqual(builder.text, "م ")
        builder.backspace()
        self.assertEqual(builder.text, "م")
        self.assertEqual(builder.clear(), "")

    def test_rejects_non_single_character(self):
        builder = TextBuilderService()
        with self.assertRaises(ValueError):
            builder.add_letter("سلام")


if __name__ == "__main__":
    unittest.main()
