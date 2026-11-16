import unittest

from text_utils import slugify


class SlugifyTests(unittest.TestCase):
    def test_trims_and_removes_punctuation(self):
        self.assertEqual(slugify("  Hello, World!  "), "hello-world")

    def test_collapses_non_alphanumeric_spans(self):
        self.assertEqual(slugify("Python__API v2"), "python-api-v2")


if __name__ == "__main__":
    unittest.main()
