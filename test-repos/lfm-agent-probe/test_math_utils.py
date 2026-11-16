import unittest

from math_utils import clamp


class ClampTests(unittest.TestCase):
    def test_value_inside_range_is_unchanged(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_value_below_range_uses_lower_bound(self):
        self.assertEqual(clamp(-2, 0, 10), 0)

    def test_value_above_range_uses_upper_bound(self):
        self.assertEqual(clamp(15, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
