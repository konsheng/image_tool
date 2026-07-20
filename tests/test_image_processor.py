from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import image_processor
from config import MAX_OUTPUT_DIMENSION, MAX_OUTPUT_PIXELS
from image_processor import (
    ProcessOptions,
    create_canvas,
    overlay_logos,
    process_image,
    render_encoded_preview_image,
)

from tests.test_compressor import make_detailed_image


def make_options(**overrides: object) -> ProcessOptions:
    values: dict[str, object] = {
        "output_format": "JPG",
        "output_size": None,
        "target_size": None,
        "apply_logo": False,
        "logos": [],
        "watermark_options": None,
        "quality": None,
    }
    values.update(overrides)
    return ProcessOptions(**values)  # type: ignore[arg-type]


class ProcessOptionsTestCase(unittest.TestCase):
    def test_target_size_and_quality_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            make_options(target_size=100_000, quality=80)

    def test_quality_must_be_in_supported_range(self) -> None:
        for quality in (0, 101):
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    make_options(quality=quality)

    def test_output_size_rejects_oversized_side_before_allocating(self) -> None:
        with self.assertRaisesRegex(ValueError, "per side"):
            make_options(output_size=(MAX_OUTPUT_DIMENSION + 1, 1))

        with self.assertRaisesRegex(ValueError, "per side"):
            create_canvas(
                Image.new("RGB", (1, 1)),
                (1, MAX_OUTPUT_DIMENSION + 1),
            )

    def test_output_size_rejects_excessive_total_pixels(self) -> None:
        height = MAX_OUTPUT_PIXELS // MAX_OUTPUT_DIMENSION + 1
        self.assertLessEqual(height, MAX_OUTPUT_DIMENSION)
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            make_options(output_size=(MAX_OUTPUT_DIMENSION, height))

    def test_output_size_requires_positive_integer_dimensions(self) -> None:
        for output_size in ((0, 100), (100, -1), (True, 100), (1.5, 100)):
            with self.subTest(output_size=output_size):
                with self.assertRaisesRegex(ValueError, "positive integers"):
                    make_options(output_size=output_size)  # type: ignore[arg-type]


class ImageCompositionTestCase(unittest.TestCase):
    def test_overlay_logo_preserves_source_alpha_on_transparent_base(self) -> None:
        base = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
        logo = Image.new("RGBA", (2, 2), (240, 80, 20, 128))

        result = overlay_logos(base, [logo])

        self.assertEqual(result.mode, "RGBA")
        self.assertEqual(result.getpixel((0, 0)), (240, 80, 20, 128))

    def test_large_tile_offsets_are_periodic_and_iteration_is_bounded(self) -> None:
        layer = Image.new("RGBA", (3, 2), (20, 100, 220, 128))
        spacing_x, spacing_y = 2, 3
        step_x = layer.width + spacing_x
        step_y = layer.height + spacing_y
        offset_x = -10**12 - 37
        offset_y = 10**12 + 41
        normalized_x = image_processor._normalize_tile_offset(offset_x, step_x)
        normalized_y = image_processor._normalize_tile_offset(offset_y, step_y)
        actual = Image.new("RGBA", (23, 19), (0, 0, 0, 0))
        expected = Image.new("RGBA", actual.size, (0, 0, 0, 0))

        with patch.object(
            image_processor,
            "_alpha_composite_clipped",
            wraps=image_processor._alpha_composite_clipped,
        ) as composite:
            image_processor._paste_tiled(
                actual,
                layer,
                spacing_x,
                spacing_y,
                offset_x,
                offset_y,
            )

        image_processor._paste_tiled(
            expected,
            layer,
            spacing_x,
            spacing_y,
            normalized_x,
            normalized_y,
        )
        max_columns = (actual.width + step_x - 1) // step_x + 1
        max_rows = (actual.height + step_y - 1) // step_y + 1

        self.assertEqual(actual.tobytes(), expected.tobytes())
        self.assertLessEqual(composite.call_count, max_columns * max_rows)


class EncodedProcessingTestCase(unittest.TestCase):
    def test_process_image_uses_manual_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            target = root / "output.jpg"
            make_detailed_image().save(source, format="PNG")
            options = make_options(quality=31)

            result = process_image(source, target, options)

            self.assertEqual(result.compression.quality, 31)
            self.assertEqual(result.output_size, target.stat().st_size)
            self.assertEqual(result.output_size, len(result.compression.data))
            with Image.open(target) as decoded:
                self.assertEqual(decoded.format, "JPEG")
                self.assertEqual(decoded.size, (80, 80))
                decoded.load()

    def test_render_encoded_preview_returns_decoded_image_and_true_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            original = make_detailed_image()
            original.save(source, format="PNG")
            options = make_options(quality=8)

            preview = render_encoded_preview_image(source, options)

            self.assertEqual(preview.compression.quality, 8)
            self.assertEqual(preview.compression.size, len(preview.compression.data))
            preview.image.load()
            self.assertEqual(preview.image.size, original.size)

            with Image.open(BytesIO(preview.compression.data)) as encoded:
                encoded.load()
                expected_pixels = encoded.convert("RGB").tobytes()
            self.assertEqual(preview.image.convert("RGB").tobytes(), expected_pixels)
            self.assertNotEqual(preview.image.convert("RGB").tobytes(), original.tobytes())

    def test_png_encoded_preview_ignores_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            original = make_detailed_image((24, 24))
            original.save(source, format="PNG")
            options = make_options(output_format="PNG", quality=50)

            preview = render_encoded_preview_image(source, options)

            self.assertIsNone(preview.compression.quality)
            self.assertEqual(preview.compression.size, len(preview.compression.data))
            preview.image.load()
            self.assertEqual(preview.image.size, original.size)


if __name__ == "__main__":
    unittest.main()
