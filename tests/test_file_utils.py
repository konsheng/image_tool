from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from file_utils import (
    MAX_FILENAME_SUFFIX_LENGTH,
    build_default_output_path,
    build_output_file_stem,
    bytes_to_display,
    ensure_unique_path,
    normalize_filename_suffix,
)


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

    def test_custom_filename_suffix_is_normalized_and_replaces_logo_names(self) -> None:
        self.assertEqual(normalize_filename_suffix("  _电商图  "), "电商图")
        self.assertEqual(
            build_output_file_stem(
                Path("原图.jpg"),
                ["生润食品", "配送到家"],
                "_电商图",
            ),
            "原图_电商图",
        )

    def test_empty_custom_suffix_preserves_existing_filename_rules(self) -> None:
        self.assertEqual(build_output_file_stem(Path("原图.jpg")), "原图_已处理")
        self.assertEqual(
            build_output_file_stem(Path("原图.jpg"), ["生润食品"], ""),
            "原图_生润食品",
        )

    def test_custom_suffix_precedes_collision_number(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "原图_电商图.jpg"
            existing.touch()

            output = build_default_output_path(
                Path("原图.png"),
                temp_dir,
                "JPG",
                custom_suffix="电商图",
            )

            self.assertEqual(output.name, "原图_电商图_1.jpg")

    def test_custom_filename_suffix_rejects_invalid_values(self) -> None:
        for invalid_value in ("推广/主图", "推广*主图", "推广\n主图"):
            with self.subTest(value=invalid_value):
                with self.assertRaisesRegex(ValueError, "文件名后缀不能包含"):
                    normalize_filename_suffix(invalid_value)

        with self.assertRaisesRegex(ValueError, "不能超过"):
            normalize_filename_suffix("图" * (MAX_FILENAME_SUFFIX_LENGTH + 1))

        self.assertEqual(
            normalize_filename_suffix("图" * MAX_FILENAME_SUFFIX_LENGTH),
            "图" * MAX_FILENAME_SUFFIX_LENGTH,
        )
        with self.assertRaisesRegex(ValueError, "不能只包含下划线"):
            normalize_filename_suffix("___")
        with self.assertRaisesRegex(ValueError, "无需填写图片扩展名"):
            normalize_filename_suffix("电商图.JPG")
        with self.assertRaisesRegex(ValueError, "不能以句点结尾"):
            normalize_filename_suffix("电商图.")

    def test_output_filename_length_counts_utf16_units(self) -> None:
        oversized_name = f"{'😀' * 126}.jpg"
        self.assertLessEqual(len(oversized_name), 255)
        with self.assertRaisesRegex(ValueError, "输出文件名过长"):
            ensure_unique_path(Path(oversized_name))


if __name__ == "__main__":
    unittest.main()
