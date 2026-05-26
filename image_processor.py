from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from compressor import CompressionResult, compress_image_to_bytes, save_image_to_bytes
from config import WATERMARK_POSITION_CUSTOM, WATERMARK_POSITION_TILE, WATERMARK_TYPE_IMAGE, WATERMARK_TYPE_TEXT
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
class ProcessOptions:
    output_format: str
    output_size: tuple[int, int] | None
    target_size: int | None
    apply_logo: bool
    logos: list[Image.Image]
    watermark_options: WatermarkOptions | None = None


@dataclass(frozen=True)
class ProcessResult:
    output_path: Path
    output_size: int
    exceeded: bool
    compression: CompressionResult
    dimensions: tuple[int, int]


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
    source = Path(source_path)
    target = Path(output_path)

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

    if options.watermark_options is not None:
        working = apply_watermark(working, options.watermark_options)

    if options.target_size is None:
        compression = save_image_to_bytes(working, options.output_format)
    else:
        compression = compress_image_to_bytes(working, options.output_format, options.target_size)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(compression.data)

    return ProcessResult(
        output_path=target,
        output_size=compression.size,
        exceeded=compression.exceeded,
        compression=compression,
        dimensions=working.size,
    )


def render_preview_image(source_path: str | Path, options: ProcessOptions) -> Image.Image:
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

    if options.watermark_options is not None:
        working = apply_watermark(working, options.watermark_options)

    return _preview_display_image(working)


def create_canvas(image: Image.Image, output_size: tuple[int, int]) -> Image.Image:
    width, height = output_size
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
    result = image.convert("RGBA") if has_alpha else image.convert("RGB")

    for logo in logos:
        logo_image = logo.convert("RGBA")
        if logo_image.size != result.size:
            logo_image = logo_image.resize(result.size, Image.Resampling.LANCZOS)
        result.paste(logo_image, (0, 0), logo_image)

    return result


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
    start_x = offset_x
    start_y = offset_y

    while start_x > 0:
        start_x -= step_x
    while start_y > 0:
        start_y -= step_y

    y = start_y
    while y < overlay.height:
        x = start_x
        while x < overlay.width:
            _alpha_composite_clipped(overlay, layer, x, y)
            x += step_x
        y += step_y


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


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
