from __future__ import annotations

import unittest

from config import (
    BLIND_WATERMARK_ACTION_EMBED,
    BLIND_WATERMARK_ACTION_EXTRACT,
    BLIND_WATERMARK_ACTIONS,
    BLIND_WATERMARK_BIT_LENGTH_STEP,
    BLIND_WATERMARK_FRAME_OVERHEAD_BYTES,
    COMPREHENSIVE_FEATURE_DEFAULTS,
    DEFAULT_BLIND_WATERMARK_ACTION,
    DEFAULT_BLIND_WATERMARK_CONTENT_KEY,
    DEFAULT_BLIND_WATERMARK_IMAGE_KEY,
    DEFAULT_BLIND_WATERMARK_TEXT,
    DEFAULT_MANUAL_QUALITY,
    FEATURE_BLIND_WATERMARK,
    FEATURE_DEFAULTS,
    FEATURE_LABELS,
    FEATURE_REFERENCE_NOTICE,
    FEATURE_WATERMARK,
    MAX_BLIND_WATERMARK_BIT_LENGTH,
    MAX_BLIND_WATERMARK_KEY,
    MAX_BLIND_WATERMARK_TEXT_BYTES,
    MAX_MANUAL_QUALITY,
    MIN_BLIND_WATERMARK_BIT_LENGTH,
    MIN_BLIND_WATERMARK_IMAGE_EDGE,
    MIN_BLIND_WATERMARK_KEY,
    MIN_MANUAL_QUALITY,
)


class CompressionDefaultsTestCase(unittest.TestCase):
    def test_manual_quality_defaults_to_95_with_full_supported_range(self) -> None:
        self.assertEqual(DEFAULT_MANUAL_QUALITY, 95)
        self.assertEqual(MIN_MANUAL_QUALITY, 1)
        self.assertEqual(MAX_MANUAL_QUALITY, 100)

    def test_optional_watermark_features_are_disabled_by_default(self) -> None:
        disabled_by_default = {
            FEATURE_WATERMARK,
            FEATURE_REFERENCE_NOTICE,
            FEATURE_BLIND_WATERMARK,
        }
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

    def test_blind_watermark_defaults_and_limits_are_consistent(self) -> None:
        self.assertEqual(FEATURE_LABELS[FEATURE_BLIND_WATERMARK], "盲水印")
        self.assertEqual(
            BLIND_WATERMARK_ACTIONS,
            (BLIND_WATERMARK_ACTION_EMBED, BLIND_WATERMARK_ACTION_EXTRACT),
        )
        self.assertEqual(DEFAULT_BLIND_WATERMARK_ACTION, BLIND_WATERMARK_ACTION_EMBED)
        self.assertEqual(DEFAULT_BLIND_WATERMARK_TEXT, "图片处理工具")
        self.assertLessEqual(
            len(DEFAULT_BLIND_WATERMARK_TEXT.encode("utf-8")),
            MAX_BLIND_WATERMARK_TEXT_BYTES,
        )
        self.assertEqual(DEFAULT_BLIND_WATERMARK_IMAGE_KEY, 2026)
        self.assertEqual(DEFAULT_BLIND_WATERMARK_CONTENT_KEY, 2026)
        self.assertEqual(MIN_BLIND_WATERMARK_KEY, 1)
        self.assertEqual(MAX_BLIND_WATERMARK_KEY, 2**32 - 1)
        self.assertEqual(MAX_BLIND_WATERMARK_TEXT_BYTES, 32)
        self.assertEqual(BLIND_WATERMARK_FRAME_OVERHEAD_BYTES, 13)
        self.assertEqual(MIN_BLIND_WATERMARK_BIT_LENGTH, 112)
        self.assertEqual(MAX_BLIND_WATERMARK_BIT_LENGTH, 360)
        self.assertEqual(BLIND_WATERMARK_BIT_LENGTH_STEP, 8)
        self.assertEqual(MIN_BLIND_WATERMARK_IMAGE_EDGE, 256)
        self.assertEqual(MIN_BLIND_WATERMARK_BIT_LENGTH % 8, 0)
        self.assertEqual(MAX_BLIND_WATERMARK_BIT_LENGTH % 8, 0)
        self.assertEqual(
            (
                len(DEFAULT_BLIND_WATERMARK_TEXT.encode("utf-8"))
                + BLIND_WATERMARK_FRAME_OVERHEAD_BYTES
            )
            * 8,
            248,
        )


if __name__ == "__main__":
    unittest.main()
