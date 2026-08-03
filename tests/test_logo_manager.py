from __future__ import annotations

import unittest
from pathlib import Path

from file_utils import build_output_file_stem
from logo_manager import LogoAsset, strip_logo_display_index


class LogoAssetNameTestCase(unittest.TestCase):
    def test_display_index_is_removed_from_output_name(self) -> None:
        asset = LogoAsset(name="01生润食品", path=Path("01生润食品.png"))

        self.assertEqual(asset.name, "01生润食品")
        self.assertEqual(asset.output_name, "生润食品")

    def test_common_separator_after_display_index_is_removed(self) -> None:
        self.assertEqual(strip_logo_display_index("02_冰润鲜"), "冰润鲜")
        self.assertEqual(strip_logo_display_index("03-配送到家"), "配送到家")

    def test_output_filename_uses_names_without_display_indexes(self) -> None:
        assets = [
            LogoAsset(name="01生润食品", path=Path("01生润食品.png")),
            LogoAsset(name="02冰润鲜", path=Path("02冰润鲜.png")),
        ]

        output_stem = build_output_file_stem(
            Path("原图.jpg"),
            [asset.output_name for asset in assets],
        )

        self.assertEqual(output_stem, "原图_生润食品_冰润鲜")

    def test_non_display_numbers_are_preserved(self) -> None:
        self.assertEqual(strip_logo_display_index("360品牌"), "360品牌")
        self.assertEqual(strip_logo_display_index("01"), "01")


if __name__ == "__main__":
    unittest.main()
