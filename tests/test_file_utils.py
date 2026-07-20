from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from file_utils import bytes_to_display, ensure_unique_path


class EnsureUniquePathTestCase(unittest.TestCase):
    def test_empty_reserved_set_tracks_and_avoids_duplicate_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reserved: set[str] = set()
            requested = Path(temp_dir) / "same-name.jpg"

            first = ensure_unique_path(requested, reserved)
            second = ensure_unique_path(requested, reserved)

            self.assertNotEqual(first, second)
            self.assertEqual(len(reserved), 2)

    def test_bytes_to_display_supports_cumulative_sizes(self) -> None:
        self.assertEqual(bytes_to_display(8_600_000_000), "8.6GB")
        self.assertEqual(bytes_to_display(12_500_000_000_000), "12.5TB")


if __name__ == "__main__":
    unittest.main()
