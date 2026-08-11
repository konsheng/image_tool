from __future__ import annotations

import unittest

from config import (
    COMPREHENSIVE_FEATURE_DEFAULTS,
    DEFAULT_MANUAL_QUALITY,
    FEATURE_DEFAULTS,
    FEATURE_REFERENCE_NOTICE,
    FEATURE_WATERMARK,
    MAX_MANUAL_QUALITY,
    MIN_MANUAL_QUALITY,
)


class CompressionDefaultsTestCase(unittest.TestCase):
    def test_manual_quality_defaults_to_95_with_full_supported_range(self) -> None:
        self.assertEqual(DEFAULT_MANUAL_QUALITY, 95)
        self.assertEqual(MIN_MANUAL_QUALITY, 1)
        self.assertEqual(MAX_MANUAL_QUALITY, 100)

    def test_optional_watermark_and_reference_notice_are_disabled_by_default(self) -> None:
        disabled_by_default = {FEATURE_WATERMARK, FEATURE_REFERENCE_NOTICE}
        for feature in disabled_by_default:
            self.assertFalse(FEATURE_DEFAULTS[feature])
            self.assertFalse(COMPREHENSIVE_FEATURE_DEFAULTS[feature])
        self.assertTrue(
            all(
                enabled
                for feature, enabled in FEATURE_DEFAULTS.items()
                if feature not in disabled_by_default
            )
        )
        self.assertTrue(
            all(
                enabled
                for feature, enabled in COMPREHENSIVE_FEATURE_DEFAULTS.items()
                if feature not in disabled_by_default
            )
        )


if __name__ == "__main__":
    unittest.main()
