from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from file_utils import ensure_unique_path


class EnsureUniquePathTestCase(unittest.TestCase):
    def test_empty_reserved_set_tracks_and_avoids_duplicate_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reserved: set[str] = set()
            requested = Path(temp_dir) / "same-name.jpg"

            first = ensure_unique_path(requested, reserved)
            second = ensure_unique_path(requested, reserved)

            self.assertNotEqual(first, second)
            self.assertEqual(len(reserved), 2)


if __name__ == "__main__":
    unittest.main()
