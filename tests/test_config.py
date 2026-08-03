from __future__ import annotations

import unittest

from config import (
    DEFAULT_MANUAL_QUALITY,
    FEATURE_DEFAULTS,
    FEATURE_WATERMARK,
    MAX_MANUAL_QUALITY,
    MIN_MANUAL_QUALITY,
)


class CompressionDefaultsTestCase(unittest.TestCase):
    def test_manual_quality_defaults_to_95_with_full_supported_range(self) -> None:
        self.assertEqual(DEFAULT_MANUAL_QUALITY, 95)
        self.assertEqual(MIN_MANUAL_QUALITY, 1)
        self.assertEqual(MAX_MANUAL_QUALITY, 100)

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
