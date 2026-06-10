from pathlib import Path
import unittest

from media_toolkit.path_input import normalize_directory_input


class PathInputTest(unittest.TestCase):
    def test_normalizes_quoted_path(self):
        self.assertEqual(
            normalize_directory_input('"/tmp/media import"'),
            Path("/tmp/media import").resolve(),
        )

    def test_normalizes_shell_escaped_spaces(self):
        self.assertEqual(
            normalize_directory_input(r"/tmp/media\ import"),
            Path("/tmp/media import").resolve(),
        )


if __name__ == "__main__":
    unittest.main()
