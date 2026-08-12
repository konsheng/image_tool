from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace
from io import BytesIO
from math import cos, pi, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from blind_watermark_service import BlindWatermarkOptions, embed_blind_watermark
from compressor import CompressionResult, save_image_to_bytes
from config import (
    DEFAULT_REFERENCE_NOTICE_BACKGROUND_OPACITY,
    DEFAULT_REFERENCE_NOTICE_POSITION,
    MAX_OUTPUT_DIMENSION,
    MAX_OUTPUT_PIXELS,
    MAX_MANUAL_QUALITY,
    MAX_REFERENCE_NOTICE_TEXT_LENGTH,
    MIN_MANUAL_QUALITY,
    REFERENCE_NOTICE_POSITIONS,
    REFERENCE_NOTICE_POSITION_BOTTOM_LEFT,
    REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT,
    REFERENCE_NOTICE_POSITION_TOP_LEFT,
    REFERENCE_NOTICE_POSITION_TOP_RIGHT,
    WATERMARK_POSITION_CUSTOM,
    WATERMARK_POSITION_TILE,
    WATERMARK_TYPE_IMAGE,
    WATERMARK_TYPE_TEXT,
)
from file_utils import get_file_size


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    file_name: str
    image_format: str
    width: int | None
    height: int | None
    size_bytes: int


@dataclass(frozen=True)
class WatermarkOptions:
    watermark_type: str
    text: str = ""
    image: Image.Image | None = None
    color: tuple[int, int, int] = (102, 102, 102)
    opacity: int = 35
    position: str = "右下"
    margin: int = 40
    font_size: int = 48
    image_scale: int = 20
    angle: int = 0
    offset_x: int = 0
    offset_y: int = 0
    tile_spacing_x: int = 80
    tile_spacing_y: int = 80
    tile_offset_x: int = 40
    tile_offset_y: int = 40


@dataclass(frozen=True)
class ReferenceNoticeOptions:
    text: str
    font_path: str | Path
    font_size: int = 0
    background_opacity: int = DEFAULT_REFERENCE_NOTICE_BACKGROUND_OPACITY
    position: str = DEFAULT_REFERENCE_NOTICE_POSITION

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("reference notice text cannot be empty")
        if len(self.text) > MAX_REFERENCE_NOTICE_TEXT_LENGTH:
            raise ValueError(
                "reference notice text cannot exceed "
                f"{MAX_REFERENCE_NOTICE_TEXT_LENGTH} characters"
            )

        if (
            isinstance(self.font_size, bool)
            or not isinstance(self.font_size, int)
            or not (self.font_size == 0 or 1 <= self.font_size <= 500)
        ):
            raise ValueError("reference notice font_size must be 0 or between 1 and 500")

        if (
            isinstance(self.background_opacity, bool)
            or not isinstance(self.background_opacity, int)
            or not 1 <= self.background_opacity <= 100
        ):
            raise ValueError("reference notice background_opacity must be between 1 and 100")

        if self.position not in REFERENCE_NOTICE_POSITIONS:
            raise ValueError("reference notice position is invalid")

        try:
            font_path = Path(self.font_path)
        except TypeError as exc:
            raise ValueError("reference notice font_path must be a file path") from exc
        if not font_path.is_file():
            raise ValueError(f"参考图提示字体文件不存在：{font_path}")


@dataclass(frozen=True)
class ProcessOptions:
    output_format: str
    output_size: tuple[int, int] | None
    apply_logo: bool
    logos: list[Image.Image]
    watermark_options: WatermarkOptions | None = None
    quality: int | None = None
    reference_notice_options: ReferenceNoticeOptions | None = None
    blind_watermark_options: BlindWatermarkOptions | None = None

    def __post_init__(self) -> None:
        if self.output_size is not None:
            _validate_output_size(self.output_size)
        if self.quality is not None:
            if isinstance(self.quality, bool) or not isinstance(self.quality, int):
                raise ValueError("quality must be an integer")
            if not MIN_MANUAL_QUALITY <= self.quality <= MAX_MANUAL_QUALITY:
                raise ValueError(
                    f"quality must be between {MIN_MANUAL_QUALITY} and {MAX_MANUAL_QUALITY}"
                )


@dataclass(frozen=True)
class ProcessResult:
    output_path: Path
    output_size: int
    compression: CompressionResult
    dimensions: tuple[int, int]


@dataclass(frozen=True)
class EncodedPreviewResult:
    image: Image.Image
    compression: CompressionResult


def get_image_info(path: str | Path) -> ImageInfo:
    image_path = Path(path)
    size_bytes = get_file_size(image_path)
    with Image.open(image_path) as image:
        return ImageInfo(
            path=image_path,
            file_name=image_path.name,
            image_format=(image.format or image_path.suffix.lstrip(".")).upper(),
            width=image.width,
            height=image.height,
            size_bytes=size_bytes,
        )


def process_image(source_path: str | Path, output_path: str | Path, options: ProcessOptions) -> ProcessResult:
    target = Path(output_path)
    working = _render_working_image(source_path, options)
    if options.blind_watermark_options is not None:
        working = embed_blind_watermark(
            working,
            options.blind_watermark_options,
        )
    compression = _encode_working_image(working, options)

    _atomic_write_bytes(target, compression.data)

    return ProcessResult(
        output_path=target,
        output_size=compression.size,
        compression=compression,
        dimensions=working.size,
    )


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    """Commit encoded output without exposing a partial destination file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except OSError:
            pass


def render_preview_image(source_path: str | Path, options: ProcessOptions) -> Image.Image:
    return _preview_display_image(_render_working_image(source_path, options))


def render_encoded_preview_image(
    source_path: str | Path,
    options: ProcessOptions,
) -> EncodedPreviewResult:
    working = _render_working_image(source_path, options)
    compression = _encode_working_image(working, options)

    with Image.open(BytesIO(compression.data)) as encoded:
        encoded.load()
        decoded = encoded.copy()

    return EncodedPreviewResult(
        image=_preview_display_image(decoded),
        compression=compression,
    )


def _render_working_image(source_path: str | Path, options: ProcessOptions) -> Image.Image:
    source = Path(source_path)

    try:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            working = _prepare_image(image, options.output_size)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise RuntimeError("图片无法打开") from exc

    if options.apply_logo:
        if not options.logos:
            raise RuntimeError("内置LOGO加载失败")
        working = overlay_logos(working, options.logos)

    watermark_options = options.watermark_options
    if (
        watermark_options is not None
        and options.reference_notice_options is not None
    ):
        watermark_options, _ = resolve_watermark_options_for_reference_notice(
            working.size,
            watermark_options,
            options.reference_notice_options,
        )

    if watermark_options is not None:
        working = apply_watermark(working, watermark_options)

    if options.reference_notice_options is not None:
        working = apply_reference_notice(working, options.reference_notice_options)

    return working


def _encode_working_image(image: Image.Image, options: ProcessOptions) -> CompressionResult:
    return save_image_to_bytes(image, options.output_format, quality=options.quality)


def create_canvas(image: Image.Image, output_size: tuple[int, int]) -> Image.Image:
    width, height = _validate_output_size(output_size)
    normalized = image.convert("RGBA")
    resized = ImageOps.contain(
        normalized,
        (width, height),
        method=Image.Resampling.LANCZOS,
    )

    canvas = Image.new("RGB", (width, height), "white")
    x = (width - resized.width) // 2
    y = (height - resized.height) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def overlay_logos(image: Image.Image, logos: list[Image.Image]) -> Image.Image:
    has_alpha = _has_alpha(image)
    result = image.convert("RGBA")

    for logo in logos:
        logo_image = logo.convert("RGBA")
        if logo_image.size != result.size:
            logo_image = logo_image.resize(result.size, Image.Resampling.LANCZOS)
        result = Image.alpha_composite(result, logo_image)

    return result if has_alpha else result.convert("RGB")


def apply_watermark(image: Image.Image, options: WatermarkOptions) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer = create_watermark_layer(base.size, options)

    if options.position == WATERMARK_POSITION_TILE:
        _paste_tiled(
            overlay,
            layer,
            max(0, options.tile_spacing_x),
            max(0, options.tile_spacing_y),
            options.tile_offset_x,
            options.tile_offset_y,
        )
    else:
        x, y = watermark_position_for_layer(base.size, layer.size, options)
        _alpha_composite_clipped(overlay, layer, x, y)

    watermarked = Image.alpha_composite(base, overlay)
    return watermarked.convert("RGBA") if _has_alpha(image) else watermarked.convert("RGB")


def create_watermark_layer(base_size: tuple[int, int], options: WatermarkOptions) -> Image.Image:
    if options.watermark_type == WATERMARK_TYPE_TEXT:
        layer = _create_text_watermark_layer(options)
    elif options.watermark_type == WATERMARK_TYPE_IMAGE:
        layer = _create_image_watermark_layer(base_size, options)
    else:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return _rotate_layer(layer, options.angle)


def resolve_watermark_options_for_reference_notice(
    base_size: tuple[int, int],
    watermark_options: WatermarkOptions,
    notice_options: ReferenceNoticeOptions,
) -> tuple[WatermarkOptions, bool]:
    if watermark_options.position != notice_options.position:
        return watermark_options, False

    reference_layer = create_reference_notice_layer(base_size, notice_options)
    notice_font_size = _reference_notice_font_size(
        base_size,
        notice_options.font_size,
    )
    gap = min(
        max(8, notice_font_size // 2),
        max(1, reference_layer.height // 2),
    )
    watermark_margin = max(0, watermark_options.margin)
    if notice_options.position in {
        REFERENCE_NOTICE_POSITION_BOTTOM_LEFT,
        REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT,
    }:
        highest_safe_offset_y = watermark_margin - reference_layer.height - gap
        if watermark_options.offset_y <= highest_safe_offset_y:
            return watermark_options, False
        minimum_visible_offset_y = watermark_margin - base_size[1] + 1
        adjusted_offset_y = min(
            watermark_options.offset_y,
            max(highest_safe_offset_y, minimum_visible_offset_y),
        )
    else:
        lowest_safe_offset_y = reference_layer.height + gap - watermark_margin
        if watermark_options.offset_y >= lowest_safe_offset_y:
            return watermark_options, False
        maximum_visible_offset_y = base_size[1] - watermark_margin - 1
        adjusted_offset_y = max(
            watermark_options.offset_y,
            min(lowest_safe_offset_y, maximum_visible_offset_y),
        )
    if adjusted_offset_y == watermark_options.offset_y:
        return watermark_options, False
    return replace(watermark_options, offset_y=adjusted_offset_y), True


def apply_reference_notice(
    image: Image.Image,
    options: ReferenceNoticeOptions,
    *,
    layer: Image.Image | None = None,
) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    if layer is None:
        layer = create_reference_notice_layer(base.size, options)
    x, y = reference_notice_position_for_layer(
        base.size,
        layer.size,
        options.position,
    )
    _alpha_composite_clipped(overlay, layer, x, y)

    rendered = Image.alpha_composite(base, overlay)
    return rendered.convert("RGBA") if _has_alpha(image) else rendered.convert("RGB")


def create_reference_notice_layer(
    base_size: tuple[int, int],
    options: ReferenceNoticeOptions,
) -> Image.Image:
    try:
        width, height = base_size
    except (TypeError, ValueError) as exc:
        raise ValueError("base_size must contain width and height") from exc
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("base dimensions must be positive integers")
    text = options.text.strip()
    requested_font_size = _reference_notice_font_size(
        (width, height),
        options.font_size,
    )
    (
        font,
        font_size,
        line_spacing,
        bbox,
        text_width,
        text_height,
        padding_x,
        padding_y,
    ) = _fit_reference_notice_text(
        (width, height),
        text,
        options.font_path,
        requested_font_size,
    )
    layer_width = min(width, text_width + padding_x * 2)
    layer_height = min(height, text_height + padding_y * 2)
    draw_padding_x = min(padding_x, max(0, (layer_width - text_width) // 2))
    draw_padding_y = min(padding_y, max(0, (layer_height - text_height) // 2))
    radius = min(
        max(1, round(layer_height * 0.48)),
        layer_width // 2,
        layer_height // 2,
    )

    layer = Image.new("RGBA", (layer_width, layer_height), (0, 0, 0, 0))
    _draw_reference_notice_background(
        layer,
        radius,
        options.position,
        (24, 24, 24, _opacity_to_alpha(options.background_opacity)),
    )
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.multiline_text(
        (draw_padding_x - bbox[0], draw_padding_y - bbox[1]),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        spacing=line_spacing,
    )
    return layer


def reference_notice_position_for_layer(
    base_size: tuple[int, int],
    layer_size: tuple[int, int],
    position: str,
) -> tuple[int, int]:
    if position not in REFERENCE_NOTICE_POSITIONS:
        raise ValueError("reference notice position is invalid")
    x = 0 if position in {
        REFERENCE_NOTICE_POSITION_TOP_LEFT,
        REFERENCE_NOTICE_POSITION_BOTTOM_LEFT,
    } else base_size[0] - layer_size[0]
    y = 0 if position in {
        REFERENCE_NOTICE_POSITION_TOP_LEFT,
        REFERENCE_NOTICE_POSITION_TOP_RIGHT,
    } else base_size[1] - layer_size[1]
    return x, y


def watermark_position_for_layer(
    base_size: tuple[int, int],
    layer_size: tuple[int, int],
    options: WatermarkOptions,
) -> tuple[int, int]:
    return _position_for_layer(
        base_size,
        layer_size,
        options.position,
        max(0, options.margin),
        options.offset_x,
        options.offset_y,
    )


def _prepare_image(image: Image.Image, output_size: tuple[int, int] | None) -> Image.Image:
    if output_size is not None:
        return create_canvas(image, output_size)
    return image.convert("RGBA") if _has_alpha(image) else image.convert("RGB")


def _create_text_watermark_layer(options: WatermarkOptions) -> Image.Image:
    text = options.text.strip()
    if not text:
        raise RuntimeError("请输入水印文字")

    font = _load_watermark_font(max(1, options.font_size))
    scratch = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scratch)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    padding = max(4, options.font_size // 8)

    layer = Image.new("RGBA", (width + padding * 2, height + padding * 2), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    alpha = _opacity_to_alpha(options.opacity)
    color = (*options.color, alpha)
    layer_draw.text((padding - bbox[0], padding - bbox[1]), text, font=font, fill=color)
    return layer


def _create_image_watermark_layer(base_size: tuple[int, int], options: WatermarkOptions) -> Image.Image:
    if options.image is None:
        raise RuntimeError("水印图片加载失败")

    source = options.image.convert("RGBA")
    max_width = max(1, int(base_size[0] * max(1, options.image_scale) / 100))
    max_height = max(1, int(base_size[1] * max(1, options.image_scale) / 100))
    layer = ImageOps.contain(source, (max_width, max_height), method=Image.Resampling.LANCZOS)
    alpha = layer.getchannel("A")
    opacity = max(0, min(100, options.opacity)) / 100
    alpha = alpha.point(lambda value: int(value * opacity))
    layer.putalpha(alpha)
    return layer


def _load_watermark_font(font_size: int) -> ImageFont.ImageFont:
    for font_name in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _reference_notice_font_size(base_size: tuple[int, int], requested_size: int) -> int:
    if requested_size > 0:
        return requested_size
    return max(16, min(64, round(min(base_size) * 0.025)))


def _fit_reference_notice_text(
    base_size: tuple[int, int],
    text: str,
    font_path: str | Path,
    requested_font_size: int,
) -> tuple[
    ImageFont.FreeTypeFont,
    int,
    int,
    tuple[int, int, int, int],
    int,
    int,
    int,
    int,
]:
    width, height = base_size
    scratch = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scratch)
    font_size = requested_font_size

    while True:
        font = _load_reference_notice_font(font_path, font_size)
        line_spacing = max(1, round(font_size * 0.2))
        bbox = draw.multiline_textbbox(
            (0, 0),
            text,
            font=font,
            spacing=line_spacing,
        )
        text_width = max(1, bbox[2] - bbox[0])
        text_height = max(1, bbox[3] - bbox[1])
        if font_size >= 16:
            padding_x = max(8, round(font_size * 0.5))
            padding_y = max(5, round(font_size * 0.28))
        else:
            padding_x = max(1, round(font_size * 0.5))
            padding_y = max(1, round(font_size * 0.28))

        natural_width = text_width + padding_x * 2
        natural_height = text_height + padding_y * 2
        if (natural_width <= width and natural_height <= height) or font_size == 1:
            return (
                font,
                font_size,
                line_spacing,
                bbox,
                text_width,
                text_height,
                padding_x,
                padding_y,
            )

        scale = min(width / natural_width, height / natural_height)
        font_size = max(1, min(font_size - 1, int(font_size * scale)))


def _draw_reference_notice_background(
    layer: Image.Image,
    radius: int,
    position: str,
    fill: tuple[int, int, int, int],
) -> None:
    mask = _create_reference_notice_squircle_mask(layer.size, radius, position)
    alpha = mask.point([value * fill[3] // 255 for value in range(256)])
    layer.paste((*fill[:3], 0), (0, 0, layer.width, layer.height))
    layer.putalpha(alpha)


def _create_reference_notice_squircle_mask(
    size: tuple[int, int],
    radius: int,
    position: str,
) -> Image.Image:
    """Create a single-corner n=4 superellipse mask with continuous side tangency."""
    width, height = size
    mask = Image.new("L", size, 255)
    if radius <= 0:
        return mask

    scale = min(4, max(1, 1024 // radius))
    high_side = radius * scale
    extent = high_side - 1
    corner = Image.new("L", (high_side, high_side), 0)
    corner_draw = ImageDraw.Draw(corner)
    steps = max(24, min(512, high_side))
    curve_power = 2 / 4  # Lamé exponent n=4 (a squircle), not a circular n=2 arc.
    curve: list[tuple[float, float]] = []
    for index in range(steps + 1):
        theta = (pi / 2) * (1 - index / steps)
        x = extent * (1 - cos(theta) ** curve_power)
        y = extent * (1 - sin(theta) ** curve_power)
        curve.append((x, y))
    corner_draw.polygon([*curve, (extent, extent)], fill=255)
    if scale > 1:
        corner = corner.resize((radius, radius), Image.Resampling.LANCZOS)

    if position == REFERENCE_NOTICE_POSITION_BOTTOM_RIGHT:
        corner_x, corner_y = 0, 0
    elif position == REFERENCE_NOTICE_POSITION_BOTTOM_LEFT:
        corner = corner.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        corner_x, corner_y = width - radius, 0
    elif position == REFERENCE_NOTICE_POSITION_TOP_RIGHT:
        corner = corner.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        corner_x, corner_y = 0, height - radius
    else:
        corner = corner.transpose(Image.Transpose.ROTATE_180)
        corner_x, corner_y = width - radius, height - radius
    mask.paste(corner, (corner_x, corner_y))
    return mask


def _load_reference_notice_font(
    font_path: str | Path,
    font_size: int,
) -> ImageFont.FreeTypeFont:
    path = Path(font_path)
    if not path.is_file():
        raise RuntimeError(f"参考图提示字体文件不存在：{path}")
    try:
        return ImageFont.truetype(str(path), font_size)
    except OSError as exc:
        raise RuntimeError(f"参考图提示字体无法加载：{path}") from exc


def _rotate_layer(layer: Image.Image, angle: int) -> Image.Image:
    if angle == 0:
        return layer
    return layer.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )


def _paste_tiled(
    overlay: Image.Image,
    layer: Image.Image,
    spacing_x: int,
    spacing_y: int,
    offset_x: int,
    offset_y: int,
) -> None:
    step_x = max(1, layer.width + spacing_x)
    step_y = max(1, layer.height + spacing_y)
    start_x = _normalize_tile_offset(offset_x, step_x)
    start_y = _normalize_tile_offset(offset_y, step_y)

    y = start_y
    while y < overlay.height:
        x = start_x
        while x < overlay.width:
            _alpha_composite_clipped(overlay, layer, x, y)
            x += step_x
        y += step_y


def _normalize_tile_offset(offset: int, step: int) -> int:
    """Return the equivalent tile origin nearest to, and not after, zero."""
    normalized = offset % step
    return normalized - step if normalized else 0


def _position_for_layer(
    base_size: tuple[int, int],
    layer_size: tuple[int, int],
    position: str,
    margin: int,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int]:
    base_width, base_height = base_size
    layer_width, layer_height = layer_size

    if position == WATERMARK_POSITION_CUSTOM:
        return offset_x, offset_y

    if position in {"左上", "左中", "左下"}:
        x = margin
    elif position in {"上中", "居中", "下中"}:
        x = (base_width - layer_width) // 2
    else:
        x = base_width - layer_width - margin

    if position in {"左上", "上中", "右上"}:
        y = margin
    elif position in {"左中", "居中", "右中"}:
        y = (base_height - layer_height) // 2
    else:
        y = base_height - layer_height - margin

    return x + offset_x, y + offset_y


def _alpha_composite_clipped(target: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    target_width, target_height = target.size
    layer_width, layer_height = layer.size

    left = max(0, x)
    top = max(0, y)
    right = min(target_width, x + layer_width)
    bottom = min(target_height, y + layer_height)

    if right <= left or bottom <= top:
        return

    crop_left = left - x
    crop_top = top - y
    crop_right = crop_left + (right - left)
    crop_bottom = crop_top + (bottom - top)
    target.alpha_composite(layer.crop((crop_left, crop_top, crop_right, crop_bottom)), (left, top))


def _opacity_to_alpha(opacity: int) -> int:
    return int(max(0, min(100, opacity)) / 100 * 255)


def _preview_display_image(image: Image.Image) -> Image.Image:
    if not _has_alpha(image):
        return image.convert("RGB")

    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, "white")
    canvas.paste(rgba, (0, 0), rgba)
    return canvas


def _validate_output_size(output_size: tuple[int, int]) -> tuple[int, int]:
    try:
        width, height = output_size
    except (TypeError, ValueError) as exc:
        raise ValueError("output_size must contain width and height") from exc

    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("output dimensions must be positive integers")
    if width > MAX_OUTPUT_DIMENSION or height > MAX_OUTPUT_DIMENSION:
        raise ValueError(
            f"output dimensions cannot exceed {MAX_OUTPUT_DIMENSION} pixels per side"
        )
    if width * height > MAX_OUTPUT_PIXELS:
        raise ValueError(f"output image cannot exceed {MAX_OUTPUT_PIXELS} pixels")
    return width, height


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
