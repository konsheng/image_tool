from __future__ import annotations

import unittest

from config import (
    COMPRESSION_MODE_QUALITY,
    DEFAULT_COMPRESSION_MODE,
    DEFAULT_MANUAL_QUALITY,
    FEATURE_DEFAULTS,
    FEATURE_WATERMARK,
)


class CompressionDefaultsTestCase(unittest.TestCase):
    def test_manual_quality_is_the_default_at_full_quality(self) -> None:
        self.assertEqual(DEFAULT_COMPRESSION_MODE, COMPRESSION_MODE_QUALITY)
        self.assertEqual(DEFAULT_MANUAL_QUALITY, 100)

    def test_only_watermark_is_disabled_by_default(self) -> None:
        self.assertFalse(FEATURE_DEFAULTS[FEATURE_WATERMARK])
        self.assertTrue(
            all(
                enabled
                for feature, enabled in FEATURE_DEFAULTS.items()
                if feature != FEATURE_WATERMARK
            )
        )


if __name__ == "__main__":
    unittest.main()
