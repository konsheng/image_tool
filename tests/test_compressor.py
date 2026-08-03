from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image, features

from compressor import save_image_to_bytes
from config import DEFAULT_MANUAL_QUALITY


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

    def test_jpg_uses_configured_default_quality(self) -> None:
        image = make_detailed_image()

        result = save_image_to_bytes(image, "JPG")

        self.assertEqual(result.quality, DEFAULT_MANUAL_QUALITY)
        self.assertEqual(result.detail, f"quality={DEFAULT_MANUAL_QUALITY}")
        self.assertEqual(result.size, len(result.data))
        self.assert_valid_image(result.data, "JPEG", image.size)

    def test_manual_quality_must_be_in_supported_range(self) -> None:
        image = make_detailed_image((8, 8))

        for quality in (0, 101):
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    save_image_to_bytes(image, "JPG", quality=quality)


if __name__ == "__main__":
    unittest.main()
