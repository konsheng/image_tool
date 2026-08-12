from __future__ import annotations

import unittest
from io import BytesIO

from PIL import Image

import blind_watermark_service as service
from blind_watermark_service import (
    BlindWatermarkError,
    BlindWatermarkOptions,
    embed_blind_watermark,
    extract_blind_watermark,
)
from config import (
    BLIND_WATERMARK_BIT_LENGTH_STEP,
    MAX_BLIND_WATERMARK_BIT_LENGTH,
    MIN_BLIND_WATERMARK_BIT_LENGTH,
    MIN_BLIND_WATERMARK_IMAGE_EDGE,
)


class BlindWatermarkRobustnessTestCase(unittest.TestCase):
    """Real-library regressions for the attacks this application promises."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            service._load_dependency()
        except BlindWatermarkError as exc:
            raise unittest.SkipTest(
                "blind-watermark 0.4.4 and dependencies are not installed"
            ) from exc

        size = 512
        source = Image.new("RGB", (size, size))
        source.putdata(
            [
                (
                    (x * 13 + y * 3 + (x * y) % 17) % 256,
                    (x * 5 + y * 11 + (x * y) % 29) % 256,
                    (x * 7 + y * 17 + (x * y) % 37) % 256,
                )
                for y in range(size)
                for x in range(size)
            ]
        )
        cls.options = BlindWatermarkOptions(
            text="JPEG-Q75",
            password_image=314159,
            password_watermark=271828,
        )
        cls.embedded = embed_blind_watermark(source, cls.options)

    @classmethod
    def tearDownClass(cls) -> None:
        embedded = getattr(cls, "embedded", None)
        if embedded is not None:
            embedded.close()

    def _encoded_copy(self, image_format: str, **save_options: object) -> Image.Image:
        output = BytesIO()
        self.embedded.save(output, format=image_format, **save_options)
        output.seek(0)
        with Image.open(output) as decoded:
            decoded.load()
            return decoded.copy()

    def _extract(self, image: Image.Image, **overrides: int) -> str:
        values = {
            "bit_length": self.options.bit_length,
            "password_image": self.options.password_image,
            "password_watermark": self.options.password_watermark,
        }
        values.update(overrides)
        return extract_blind_watermark(image, **values)

    def test_lossless_png_round_trip(self) -> None:
        decoded = self._encoded_copy("PNG")

        self.assertEqual(self._extract(decoded), self.options.text)

    def test_jpeg_quality_75_reencode_remains_extractable(self) -> None:
        decoded = self._encoded_copy("JPEG", quality=75)

        self.assertEqual(self._extract(decoded), self.options.text)

    def test_wrong_image_or_content_key_fails_closed(self) -> None:
        wrong_keys = (
            {"password_image": self.options.password_image + 1},
            {"password_watermark": self.options.password_watermark + 1},
        )
        for overrides in wrong_keys:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(BlindWatermarkError, "校验未通过"):
                    self._extract(self.embedded, **overrides)

    def test_multiple_wrong_valid_bit_lengths_fail_closed(self) -> None:
        wrong_bit_lengths = (
            MIN_BLIND_WATERMARK_BIT_LENGTH,
            self.options.bit_length - BLIND_WATERMARK_BIT_LENGTH_STEP,
            self.options.bit_length + BLIND_WATERMARK_BIT_LENGTH_STEP,
            MAX_BLIND_WATERMARK_BIT_LENGTH,
        )
        self.assertTrue(
            all(
                MIN_BLIND_WATERMARK_BIT_LENGTH <= bit_length <= MAX_BLIND_WATERMARK_BIT_LENGTH
                and bit_length % BLIND_WATERMARK_BIT_LENGTH_STEP == 0
                and bit_length != self.options.bit_length
                for bit_length in wrong_bit_lengths
            )
        )

        for bit_length in wrong_bit_lengths:
            with self.subTest(bit_length=bit_length):
                with self.assertRaisesRegex(BlindWatermarkError, "校验未通过"):
                    self._extract(self.embedded, bit_length=bit_length)


class BlindWatermarkShortEdgeTestCase(unittest.TestCase):
    def test_embed_and_extract_reject_images_below_the_short_edge_limit(self) -> None:
        image = Image.new(
            "RGB",
            (MIN_BLIND_WATERMARK_IMAGE_EDGE - 1, MIN_BLIND_WATERMARK_IMAGE_EDGE),
        )
        options = BlindWatermarkOptions("A", 1, 2)

        with self.assertRaisesRegex(
            ValueError,
            rf"短边至少为 {MIN_BLIND_WATERMARK_IMAGE_EDGE} 像素",
        ):
            embed_blind_watermark(image, options)

        with self.assertRaisesRegex(
            ValueError,
            rf"短边至少为 {MIN_BLIND_WATERMARK_IMAGE_EDGE} 像素",
        ):
            extract_blind_watermark(
                image,
                bit_length=options.bit_length,
                password_image=options.password_image,
                password_watermark=options.password_watermark,
            )


if __name__ == "__main__":
    unittest.main()
