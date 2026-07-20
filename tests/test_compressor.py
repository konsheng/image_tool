from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image, features

from compressor import (
    _compress_lossy_to_target,
    compress_image_to_bytes,
    save_image_to_bytes,
)


def make_detailed_image(size: tuple[int, int] = (80, 80)) -> Image.Image:
    """Return a deterministic image whose encoded size responds to quality."""
    width, height = size
    image = Image.new("RGB", size)
    image.putdata(
        [
            (
                (x * 37 + y * 17 + x * y) % 256,
                (x * 11 + y * 43 + x * y * 3) % 256,
                (x * 29 + y * 7 + x * y * 5) % 256,
            )
            for y in range(height)
            for x in range(width)
        ]
    )
    return image


class CompressionTestCase(unittest.TestCase):
    def assert_valid_image(
        self,
        data: bytes,
        expected_format: str,
        expected_size: tuple[int, int],
    ) -> None:
        with Image.open(BytesIO(data)) as decoded:
            self.assertEqual(decoded.format, expected_format)
            self.assertEqual(decoded.size, expected_size)
            decoded.load()

    def test_jpg_manual_quality_is_reported_and_used(self) -> None:
        image = make_detailed_image()

        low = save_image_to_bytes(image, "JPG", quality=20)
        high = save_image_to_bytes(image, "JPG", quality=90)

        self.assertEqual(low.quality, 20)
        self.assertEqual(high.quality, 90)
        self.assertEqual(low.size, len(low.data))
        self.assertEqual(high.size, len(high.data))
        self.assertNotEqual(low.data, high.data)
        self.assertGreater(high.size, low.size)
        self.assert_valid_image(low.data, "JPEG", image.size)
        self.assert_valid_image(high.data, "JPEG", image.size)

    @unittest.skipUnless(features.check("webp"), "Pillow was built without WebP support")
    def test_webp_manual_quality_is_reported_and_used(self) -> None:
        image = make_detailed_image()

        low = save_image_to_bytes(image, "WEBP", quality=20)
        high = save_image_to_bytes(image, "WEBP", quality=90)

        self.assertEqual(low.quality, 20)
        self.assertEqual(high.quality, 90)
        self.assertEqual(low.size, len(low.data))
        self.assertEqual(high.size, len(high.data))
        self.assertNotEqual(low.data, high.data)
        self.assertGreater(high.size, low.size)
        self.assert_valid_image(low.data, "WEBP", image.size)
        self.assert_valid_image(high.data, "WEBP", image.size)

    def test_png_ignores_manual_quality(self) -> None:
        image = make_detailed_image()

        default_result = save_image_to_bytes(image, "PNG")
        manual_result = save_image_to_bytes(image, "PNG", quality=12)

        self.assertIsNone(default_result.quality)
        self.assertIsNone(manual_result.quality)
        self.assertNotIn("quality", manual_result.detail.lower())
        self.assertEqual(manual_result.data, default_result.data)
        self.assertEqual(manual_result.size, len(manual_result.data))
        self.assert_valid_image(manual_result.data, "PNG", image.size)

    def test_jpg_target_size_uses_highest_quality_that_fits(self) -> None:
        self._assert_highest_quality_that_fits("JPG")

    def test_small_jpg_checks_all_qualities_when_sizes_are_not_monotonic(self) -> None:
        self._assert_small_image_checks_all_qualities("JPG")

    @unittest.skipUnless(features.check("webp"), "Pillow was built without WebP support")
    def test_small_webp_checks_all_qualities_when_sizes_are_not_monotonic(self) -> None:
        self._assert_small_image_checks_all_qualities("WEBP")

    def test_small_solid_jpg_checks_the_full_quality_range(self) -> None:
        self._assert_small_solid_image_checks_all_qualities(
            "JPG",
            color=(56, 104, 152),
            target_size=557,
        )

    @unittest.skipUnless(features.check("webp"), "Pillow was built without WebP support")
    def test_small_solid_webp_checks_the_full_quality_range(self) -> None:
        self._assert_small_solid_image_checks_all_qualities(
            "WEBP",
            color=(14, 26, 38),
            target_size=76,
        )

    def test_large_solid_jpg_returns_globally_highest_fitting_quality(self) -> None:
        self._assert_large_solid_image_uses_global_highest(
            "JPG",
            color=(17, 83, 149),
        )

    @unittest.skipUnless(features.check("webp"), "Pillow was built without WebP support")
    def test_large_solid_webp_returns_globally_highest_fitting_quality(self) -> None:
        self._assert_large_solid_image_uses_global_highest(
            "WEBP",
            color=(17, 83, 149),
        )

    def _assert_small_image_checks_all_qualities(self, output_format: str) -> None:
        image = make_detailed_image((8, 8))
        encoded_by_quality = {
            quality: save_image_to_bytes(image, output_format, quality=quality)
            for quality in range(1, 96)
        }
        target_size = encoded_by_quality[40].size
        expected_quality = max(
            quality
            for quality, result in encoded_by_quality.items()
            if result.size <= target_size
        )

        result = compress_image_to_bytes(image, output_format, target_size)

        self.assertFalse(result.exceeded)
        self.assertEqual(result.quality, expected_quality)
        self.assertLessEqual(result.size, target_size)

    def _assert_small_solid_image_checks_all_qualities(
        self,
        output_format: str,
        color: tuple[int, int, int],
        target_size: int,
    ) -> None:
        image = Image.new("RGB", (65, 65), color)
        encoded_by_quality = {
            quality: save_image_to_bytes(image, output_format, quality=quality)
            for quality in range(1, 96)
        }
        fitting = [
            quality
            for quality, result in encoded_by_quality.items()
            if result.size <= target_size
        ]
        self.assertTrue(fitting)

        result = compress_image_to_bytes(image, output_format, target_size)

        self.assertFalse(result.exceeded)
        self.assertEqual(result.quality, max(fitting))
        self.assertLessEqual(result.size, target_size)

    def _assert_large_solid_image_uses_global_highest(
        self,
        output_format: str,
        color: tuple[int, int, int],
    ) -> None:
        # 257 x 257 previously crossed the fast-search threshold.  Solid
        # images also expose real non-monotonic JPEG/WebP size curves.
        image = Image.new("RGB", (257, 257), color)
        encoded_by_quality = {
            quality: save_image_to_bytes(image, output_format, quality=quality)
            for quality in range(1, 96)
        }
        target_size = encoded_by_quality[60].size
        expected_quality = max(
            quality
            for quality, result in encoded_by_quality.items()
            if result.size <= target_size
        )

        result = compress_image_to_bytes(image, output_format, target_size)

        self.assertFalse(result.exceeded)
        self.assertEqual(result.quality, expected_quality)
        self.assertLessEqual(result.size, target_size)

    @unittest.skipUnless(features.check("webp"), "Pillow was built without WebP support")
    def test_webp_target_size_uses_highest_quality_that_fits(self) -> None:
        self._assert_highest_quality_that_fits("WEBP")

    def _assert_highest_quality_that_fits(self, output_format: str) -> None:
        image = make_detailed_image()
        encoded_by_quality = {
            quality: save_image_to_bytes(image, output_format, quality=quality)
            for quality in range(1, 96)
        }
        # Pick a useful middle-sized target rather than relying on a hard-coded
        # byte count, which varies across Pillow/libjpeg/libwebp releases.
        target_size = encoded_by_quality[60].size
        fitting = [
            quality
            for quality, result in encoded_by_quality.items()
            if result.size <= target_size
        ]
        self.assertTrue(fitting)
        expected_quality = max(fitting)
        self.assertLess(expected_quality, 95)

        result = compress_image_to_bytes(image, output_format, target_size)

        self.assertFalse(result.exceeded)
        self.assertEqual(result.quality, expected_quality)
        self.assertLessEqual(result.size, target_size)
        self.assertEqual(result.size, len(result.data))
        self.assert_valid_image(
            result.data,
            "JPEG" if output_format == "JPG" else output_format,
            image.size,
        )

    def test_target_too_small_returns_exceeded_result(self) -> None:
        image = make_detailed_image((32, 32))
        encoded_by_quality = {
            quality: save_image_to_bytes(image, "JPG", quality=quality)
            for quality in range(1, 96)
        }
        smallest_size = min(result.size for result in encoded_by_quality.values())
        expected_quality = max(
            quality
            for quality, result in encoded_by_quality.items()
            if result.size == smallest_size
        )

        result = compress_image_to_bytes(image, "JPG", target_size=1)

        self.assertTrue(result.exceeded)
        self.assertEqual(result.quality, expected_quality)
        self.assertEqual(result.size, smallest_size)
        self.assertGreater(result.size, 1)
        self.assertEqual(result.size, len(result.data))
        self.assert_valid_image(result.data, "JPEG", image.size)

    def test_target_search_checks_all_qualities_before_reporting_exceeded(self) -> None:
        sizes = {quality: 80 for quality in range(1, 96)}
        sizes[95] = 78
        sizes[54] = 74

        result = _compress_lossy_to_target(
            lambda quality: bytes(sizes[quality]),
            target_size=74,
        )

        self.assertFalse(result.exceeded)
        self.assertEqual(result.quality, 54)
        self.assertEqual(result.size, 74)

    def test_target_search_crosses_nonfitting_gap_for_higher_quality(self) -> None:
        sizes = {quality: 101 for quality in range(1, 96)}
        sizes[1] = 100
        sizes[93] = 100

        result = _compress_lossy_to_target(
            lambda quality: bytes(sizes[quality]),
            target_size=100,
        )

        self.assertFalse(result.exceeded)
        self.assertEqual(result.quality, 93)
        self.assertEqual(result.size, 100)

    def test_png_target_result_has_no_quality(self) -> None:
        image = make_detailed_image((32, 32))

        result = compress_image_to_bytes(image, "PNG", target_size=1)

        self.assertTrue(result.exceeded)
        self.assertIsNone(result.quality)
        self.assertEqual(result.size, len(result.data))
        self.assert_valid_image(result.data, "PNG", image.size)

    def test_manual_quality_must_be_in_supported_range(self) -> None:
        image = make_detailed_image((8, 8))

        for quality in (0, 101):
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    save_image_to_bytes(image, "JPG", quality=quality)


if __name__ == "__main__":
    unittest.main()
