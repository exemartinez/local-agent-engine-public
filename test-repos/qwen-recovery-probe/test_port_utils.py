import unittest

from port_utils import parse_port


class ParsePortTests(unittest.TestCase):
    def test_accepts_numeric_text(self):
        self.assertEqual(parse_port("8080"), 8080)

    def test_rejects_zero(self):
        with self.assertRaises(ValueError):
            parse_port(0)

    def test_rejects_too_large_port(self):
        with self.assertRaises(ValueError):
            parse_port(65536)


if __name__ == "__main__":
    unittest.main()
