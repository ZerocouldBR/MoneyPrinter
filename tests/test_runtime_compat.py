import importlib
import os
import sys
import unittest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class RuntimeCompatTests(unittest.TestCase):
    def test_pillow_antialias_alias_exists(self) -> None:
        importlib.import_module("sitecustomize")
        from PIL import Image

        self.assertTrue(hasattr(Image, "ANTIALIAS"))


if __name__ == "__main__":
    unittest.main()
