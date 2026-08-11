from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw, ImageFont

import image_processor
from config import (
    DEFAULT_MANUAL_QUALITY,
    DEFAULT_REFERENCE_NOTICE_BACKGROUND_OPACITY,
    DEFAULT_REFERENCE_NOTICE_POSITION,
    DEFAULT_REFERENCE_NOTICE_TEXT,
    DEFAULT_WATERMARK_POSITION,
    MAX_OUTPUT_DIMENSION,
    MAX_OUTPUT_PIXELS,
    MAX_REFERENCE_NOTICE_TEXT_LENGTH,
    REFERENCE_NOTICE_POSITIONS,
    REFERENCE_NOTICE_POSITION_BOTTOM_LEFT,
    REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT,
    REFERENCE_NOTICE_POSITION_TOP_LEFT,
    REFERENCE_NOTICE_POSITION_TOP_RIGHT,
)
from image_processor import (
    ProcessOptions,
    ReferenceNoticeOptions,
    WatermarkOptions,
    apply_reference_notice,
    create_canvas,
    create_reference_notice_layer,
    overlay_logos,
    process_image,
    reference_notice_position_for_layer,
    render_encoded_preview_image,
    render_preview_image,
    resolve_watermark_options_for_reference_notice,
)

from tests.test_compressor import make_detailed_image


def make_options(**overrides: object) -> ProcessOptions:
    values: dict[str, object] = {
        "output_format": "JPG",
        "output_size": None,
        "apply_logo": False,
        "logos": [],
        "watermark_options": None,
        "reference_notice_options": None,
        "quality": None,
    }
    values.update(overrides)
    return ProcessOptions(**values)  # type: ignore[arg-type]


class ProcessOptionsTestCase(unittest.TestCase):
    def test_reference_notice_field_preserves_legacy_positional_quality(self) -> None:
        options = ProcessOptions("JPG", None, False, [], None, 95)

        self.assertEqual(options.quality, 95)
        self.assertIsNone(options.reference_notice_options)

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


class ReferenceNoticeOptionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.font_path = Path(self.temp_dir.name) / "test-font.ttf"
        self.font_path.touch()

    def make_notice(self, **overrides: object) -> ReferenceNoticeOptions:
        values: dict[str, object] = {
            "text": "图片仅供参考",
            "font_path": self.font_path,
            "font_size": 0,
            "background_opacity": 55,
        }
        values.update(overrides)
        return ReferenceNoticeOptions(**values)  # type: ignore[arg-type]

    def test_text_cannot_be_empty(self) -> None:
        for text in ("", "   "):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "text cannot be empty"):
                    self.make_notice(text=text)

    def test_text_length_is_bounded(self) -> None:
        self.make_notice(text="图" * MAX_REFERENCE_NOTICE_TEXT_LENGTH)
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            self.make_notice(text="图" * (MAX_REFERENCE_NOTICE_TEXT_LENGTH + 1))

    def test_default_opacity_matches_application_configuration(self) -> None:
        options = ReferenceNoticeOptions("NOTICE", self.font_path)

        self.assertEqual(
            options.background_opacity,
            DEFAULT_REFERENCE_NOTICE_BACKGROUND_OPACITY,
        )
        self.assertEqual(options.position, DEFAULT_REFERENCE_NOTICE_POSITION)
        self.assertFalse(hasattr(options, "margin"))

    def test_default_notice_text_is_exact(self) -> None:
        self.assertEqual(DEFAULT_REFERENCE_NOTICE_TEXT, "广告创意 图片仅供参考")

    def test_position_accepts_only_the_four_supported_corners(self) -> None:
        self.assertEqual(
            REFERENCE_NOTICE_POSITIONS,
            ["左上", "右上", "左下", "右下"],
        )
        for position in REFERENCE_NOTICE_POSITIONS:
            with self.subTest(position=position):
                self.assertEqual(self.make_notice(position=position).position, position)

        for position in ("", "居中", "平铺", None, True):
            with self.subTest(position=position):
                with self.assertRaisesRegex(ValueError, "position is invalid"):
                    self.make_notice(position=position)

    def test_font_size_accepts_auto_or_supported_range(self) -> None:
        self.make_notice(font_size=0)
        self.make_notice(font_size=1)
        self.make_notice(font_size=500)

        for font_size in (-1, 501, True, 1.5):
            with self.subTest(font_size=font_size):
                with self.assertRaisesRegex(ValueError, "font_size"):
                    self.make_notice(font_size=font_size)

    def test_background_opacity_must_be_between_one_and_one_hundred(self) -> None:
        self.make_notice(background_opacity=1)
        self.make_notice(background_opacity=100)

        for opacity in (0, 101, True, 2.5):
            with self.subTest(opacity=opacity):
                with self.assertRaisesRegex(ValueError, "background_opacity"):
                    self.make_notice(background_opacity=opacity)

    def test_missing_font_path_has_clear_error(self) -> None:
        missing = Path(self.temp_dir.name) / "missing-font.otf"

        with self.assertRaisesRegex(ValueError, "字体文件不存在"):
            self.make_notice(font_path=missing)

    def test_unreadable_font_file_has_clear_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "字体无法加载"):
            create_reference_notice_layer((400, 300), self.make_notice())


class ReferenceNoticeRenderingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.font_path = Path(self.temp_dir.name) / "mock-font.ttf"
        self.font_path.touch()

    def make_notice(self, **overrides: object) -> ReferenceNoticeOptions:
        values: dict[str, object] = {
            "text": "NOTICE",
            "font_path": self.font_path,
            "font_size": 20,
            "background_opacity": 60,
        }
        values.update(overrides)
        return ReferenceNoticeOptions(**values)  # type: ignore[arg-type]

    def test_bundled_source_han_font_renders_default_chinese_text(self) -> None:
        font_path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "fonts"
            / "SourceHanSansCN-Medium.otf"
        )
        layer = create_reference_notice_layer(
            (1200, 800),
            ReferenceNoticeOptions(
                text="图片仅供参考",
                font_path=font_path,
                font_size=32,
            ),
        )

        self.assertGreater(layer.width, layer.height)
        self.assertIsNotNone(layer.getbbox())
        self.assertGreater(max(layer.getchannel("A").getextrema()), 0)

    @staticmethod
    def default_font(size: int = 20) -> ImageFont.FreeTypeFont:
        return ImageFont.load_default(size=size)

    def test_all_positions_touch_their_edges_and_round_only_the_interior_corner(self) -> None:
        base = Image.new("RGB", (240, 180), (30, 100, 180))
        rounded_corner_names = {
            REFERENCE_NOTICE_POSITION_TOP_LEFT: "bottom_right",
            REFERENCE_NOTICE_POSITION_TOP_RIGHT: "bottom_left",
            REFERENCE_NOTICE_POSITION_BOTTOM_LEFT: "top_right",
            REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT: "top_left",
        }

        for position in REFERENCE_NOTICE_POSITIONS:
            with self.subTest(position=position):
                options = self.make_notice(position=position)
                with patch.object(
                    image_processor,
                    "_load_reference_notice_font",
                    return_value=self.default_font(),
                ):
                    layer = create_reference_notice_layer(base.size, options)
                    result = apply_reference_notice(base, options)

                x, y = reference_notice_position_for_layer(
                    base.size,
                    layer.size,
                    position,
                )
                corners = {
                    "top_left": (0, 0),
                    "top_right": (layer.width - 1, 0),
                    "bottom_left": (0, layer.height - 1),
                    "bottom_right": (layer.width - 1, layer.height - 1),
                }
                rounded_name = rounded_corner_names[position]
                background = (
                    24,
                    24,
                    24,
                    int(options.background_opacity / 100 * 255),
                )

                self.assertEqual(layer.getpixel(corners[rounded_name])[3], 0)
                for name, point in corners.items():
                    if name != rounded_name:
                        self.assertEqual(layer.getpixel(point), background)

                changed_bounds = ImageChops.difference(base, result).getbbox()
                self.assertEqual(
                    changed_bounds,
                    (x, y, x + layer.width, y + layer.height),
                )
                self.assertEqual(x, 0 if "左" in position else base.width - layer.width)
                self.assertEqual(y, 0 if "上" in position else base.height - layer.height)
                notice_pixels = result.crop(
                    (x, y, x + layer.width, y + layer.height)
                ).getdata()
                self.assertTrue(
                    any(
                        red >= 250 and green >= 250 and blue >= 250
                        for red, green, blue in notice_pixels
                    )
                )

    def test_corner_radius_is_about_half_the_badge_height(self) -> None:
        options = self.make_notice()
        with (
            patch.object(
                image_processor,
                "_load_reference_notice_font",
                return_value=self.default_font(),
            ),
            patch.object(
                image_processor,
                "_draw_reference_notice_background",
                wraps=image_processor._draw_reference_notice_background,
            ) as draw_background,
        ):
            layer = create_reference_notice_layer((240, 180), options)

        radius = draw_background.call_args.args[1]
        self.assertGreaterEqual(radius / layer.height, 0.45)
        self.assertLessEqual(radius / layer.height, 0.5)

    def test_continuous_corner_differs_from_an_ordinary_circular_arc(self) -> None:
        size = (80, 40)
        radius = 20
        squircle = image_processor._create_reference_notice_squircle_mask(
            size,
            radius,
            REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT,
        )
        circular_corner = Image.new("L", (radius, radius), 0)
        ImageDraw.Draw(circular_corner).ellipse(
            (0, 0, radius * 2, radius * 2),
            fill=255,
        )

        sample = (4, 4)
        self.assertEqual(circular_corner.getpixel(sample), 0)
        self.assertGreater(squircle.getpixel(sample), 200)
        self.assertEqual(squircle.getpixel((0, 0)), 0)
        corner_values = set(squircle.crop((0, 0, radius, radius)).getdata())
        self.assertTrue(any(0 < value < 255 for value in corner_values))

    def test_extreme_valid_text_and_font_size_never_create_an_oversized_layer(self) -> None:
        options = self.make_notice(
            text="W" * MAX_REFERENCE_NOTICE_TEXT_LENGTH,
            font_size=500,
        )
        with patch.object(
            image_processor,
            "_load_reference_notice_font",
            side_effect=lambda _path, size: self.default_font(size),
        ):
            layer = create_reference_notice_layer((100, 100), options)

        self.assertLessEqual(layer.width, 100)
        self.assertLessEqual(layer.height, 100)
        self.assertIsNotNone(layer.getchannel("A").getbbox())

    def test_one_pixel_image_still_gets_a_visible_notice_pixel(self) -> None:
        base = Image.new("RGB", (1, 1), (30, 100, 180))
        options = self.make_notice(
            text="W" * MAX_REFERENCE_NOTICE_TEXT_LENGTH,
            font_size=500,
        )
        with patch.object(
            image_processor,
            "_load_reference_notice_font",
            side_effect=lambda _path, size: self.default_font(size),
        ):
            layer = create_reference_notice_layer(base.size, options)
            result = apply_reference_notice(base, options)

        self.assertEqual(layer.size, (1, 1))
        self.assertGreater(layer.getpixel((0, 0))[3], 0)
        self.assertNotEqual(result.getpixel((0, 0)), base.getpixel((0, 0)))

    def test_notice_preserves_dimensions_and_source_alpha_mode(self) -> None:
        with patch.object(
            image_processor,
            "_load_reference_notice_font",
            return_value=self.default_font(),
        ):
            rgb_result = apply_reference_notice(
                Image.new("RGB", (180, 120), "white"),
                self.make_notice(),
            )
            rgba_result = apply_reference_notice(
                Image.new("RGBA", (180, 120), (0, 0, 0, 0)),
                self.make_notice(),
            )

        self.assertEqual(rgb_result.size, (180, 120))
        self.assertEqual(rgb_result.mode, "RGB")
        self.assertEqual(rgba_result.size, (180, 120))
        self.assertEqual(rgba_result.mode, "RGBA")

    def test_auto_font_size_uses_short_edge_and_clamps_to_supported_bounds(self) -> None:
        cases = (
            ((100, 300), 16),
            ((1000, 2000), 25),
            ((4000, 3000), 64),
        )

        for base_size, expected_size in cases:
            with self.subTest(base_size=base_size):
                with patch.object(
                    image_processor,
                    "_load_reference_notice_font",
                    return_value=self.default_font(expected_size),
                ) as load_font:
                    create_reference_notice_layer(base_size, self.make_notice(font_size=0))
                load_font.assert_called_once_with(self.font_path, expected_size)

    def test_explicit_font_size_overrides_automatic_size(self) -> None:
        with patch.object(
            image_processor,
            "_load_reference_notice_font",
            side_effect=lambda _path, size: self.default_font(size),
        ) as load_font:
            create_reference_notice_layer((1000, 1000), self.make_notice(font_size=37))

        load_font.assert_called_once_with(self.font_path, 37)

    def test_large_source_dimensions_are_not_rejected_as_output_dimensions(self) -> None:
        with patch.object(
            image_processor,
            "_load_reference_notice_font",
            return_value=self.default_font(),
        ):
            layer = create_reference_notice_layer(
                (MAX_OUTPUT_DIMENSION + 1, 100),
                self.make_notice(),
            )

        self.assertGreater(layer.width, 0)
        self.assertGreater(layer.height, 0)


class ReferenceNoticePipelineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source.png"
        Image.new("RGB", (320, 240), "white").save(self.source, format="PNG")
        self.font_path = self.root / "mock-font.ttf"
        self.font_path.touch()

    def notice_options(self, **overrides: object) -> ReferenceNoticeOptions:
        values: dict[str, object] = {
            "text": "NOTICE",
            "font_path": self.font_path,
            "font_size": 20,
            "background_opacity": 55,
        }
        values.update(overrides)
        return ReferenceNoticeOptions(**values)  # type: ignore[arg-type]

    @staticmethod
    def record_step(steps: list[str], name: str):
        def side_effect(image: Image.Image, *_args: object, **_kwargs: object) -> Image.Image:
            steps.append(name)
            return image

        return side_effect

    def test_processing_order_is_logo_watermark_notice_then_encoding(self) -> None:
        steps: list[str] = []
        watermark = WatermarkOptions(watermark_type="test", position="not-bottom-right")
        notice = self.notice_options()
        original_encode = image_processor._encode_working_image

        def encode(image: Image.Image, options: ProcessOptions):
            steps.append("encode")
            return original_encode(image, options)

        with (
            patch.object(
                image_processor,
                "overlay_logos",
                side_effect=self.record_step(steps, "logo"),
            ),
            patch.object(
                image_processor,
                "apply_watermark",
                side_effect=self.record_step(steps, "watermark"),
            ),
            patch.object(
                image_processor,
                "apply_reference_notice",
                side_effect=self.record_step(steps, "reference_notice"),
            ),
            patch.object(image_processor, "_encode_working_image", side_effect=encode),
        ):
            process_image(
                self.source,
                self.root / "output.jpg",
                make_options(
                    apply_logo=True,
                    logos=[Image.new("RGBA", (1, 1))],
                    watermark_options=watermark,
                    reference_notice_options=notice,
                ),
            )

        self.assertEqual(steps, ["logo", "watermark", "reference_notice", "encode"])

    def test_bottom_right_watermark_moves_above_notice(self) -> None:
        notice = self.notice_options()
        watermark = WatermarkOptions(
            watermark_type="test",
            position=DEFAULT_WATERMARK_POSITION,
            margin=0,
            offset_y=0,
        )
        font = ImageFont.load_default(size=notice.font_size)

        with (
            patch.object(
                image_processor,
                "_load_reference_notice_font",
                return_value=font,
            ),
            patch.object(
                image_processor,
                "apply_watermark",
                side_effect=lambda image, _options: image,
            ) as apply_watermark_mock,
        ):
            render_preview_image(
                self.source,
                make_options(
                    watermark_options=watermark,
                    reference_notice_options=notice,
                ),
            )
            expected_layer = create_reference_notice_layer((320, 240), notice)

        passed_options = apply_watermark_mock.call_args.args[1]
        expected_gap = max(8, notice.font_size // 2)
        expected_offset = watermark.margin - expected_layer.height - expected_gap
        self.assertEqual(passed_options.offset_y, expected_offset)

    def test_all_matching_corner_watermarks_shift_away_from_the_notice(self) -> None:
        top_positions = {
            REFERENCE_NOTICE_POSITION_TOP_LEFT,
            REFERENCE_NOTICE_POSITION_TOP_RIGHT,
        }
        for position in REFERENCE_NOTICE_POSITIONS:
            with self.subTest(position=position):
                notice = self.notice_options(position=position)
                watermark = WatermarkOptions(
                    watermark_type="test",
                    position=position,
                    margin=0,
                    offset_y=0,
                )
                with patch.object(
                    image_processor,
                    "_load_reference_notice_font",
                    side_effect=lambda _path, size: ImageFont.load_default(size=size),
                ):
                    resolved, shifted = resolve_watermark_options_for_reference_notice(
                        (320, 240),
                        watermark,
                        notice,
                    )

                self.assertTrue(shifted)
                if position in top_positions:
                    self.assertGreater(resolved.offset_y, watermark.offset_y)
                else:
                    self.assertLess(resolved.offset_y, watermark.offset_y)
                self.assertEqual(watermark.offset_y, 0)

    def test_insufficient_space_keeps_top_and_bottom_watermarks_on_canvas(self) -> None:
        cases = (
            (REFERENCE_NOTICE_POSITION_TOP_LEFT, 31),
            (REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT, -31),
        )
        for position, expected_offset in cases:
            with self.subTest(position=position):
                notice = ReferenceNoticeOptions(
                    text="\n".join(["W"] * 50),
                    font_path=self.font_path,
                    font_size=500,
                    background_opacity=55,
                    position=position,
                )
                watermark = WatermarkOptions(
                    watermark_type="test",
                    position=position,
                    margin=0,
                    offset_y=0,
                )
                with patch.object(
                    image_processor,
                    "_load_reference_notice_font",
                    side_effect=lambda _path, size: ImageFont.load_default(size=size),
                ):
                    reference_layer = create_reference_notice_layer((32, 32), notice)
                    resolved, shifted = resolve_watermark_options_for_reference_notice(
                        (32, 32),
                        watermark,
                        notice,
                    )

                self.assertEqual(reference_layer.height, 32)
                self.assertTrue(shifted)
                self.assertEqual(resolved.offset_y, expected_offset)
                watermark_y = (
                    watermark.margin + resolved.offset_y
                    if position == REFERENCE_NOTICE_POSITION_TOP_LEFT
                    else 32 - watermark.margin + resolved.offset_y
                )
                self.assertGreaterEqual(watermark_y, 0)
                self.assertLess(watermark_y, 32)

    def test_other_watermark_positions_are_not_shifted(self) -> None:
        notice = self.notice_options()
        watermark = WatermarkOptions(
            watermark_type="test",
            position=REFERENCE_NOTICE_POSITION_TOP_LEFT,
            margin=40,
            offset_y=7,
        )

        with (
            patch.object(
                image_processor,
                "apply_watermark",
                side_effect=lambda image, _options: image,
            ) as apply_watermark_mock,
            patch.object(
                image_processor,
                "apply_reference_notice",
                side_effect=lambda image, _options, **_kwargs: image,
            ),
        ):
            render_preview_image(
                self.source,
                make_options(
                    watermark_options=watermark,
                    reference_notice_options=notice,
                ),
            )

        passed_options = apply_watermark_mock.call_args.args[1]
        self.assertIs(passed_options, watermark)
        resolved, shifted = resolve_watermark_options_for_reference_notice(
            (320, 240),
            watermark,
            notice,
        )
        self.assertIs(resolved, watermark)
        self.assertFalse(shifted)


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
    def test_process_image_uses_default_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            target = root / "output.jpg"
            make_detailed_image().save(source, format="PNG")

            result = process_image(source, target, make_options())

            self.assertEqual(result.compression.quality, DEFAULT_MANUAL_QUALITY)

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
