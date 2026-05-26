from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from config import PNG_PALETTE_COLORS, QUALITY_STEPS


@dataclass(frozen=True)
class CompressionResult:
    data: bytes
    size: int
    exceeded: bool
    detail: str


def compress_image_to_bytes(image: Image.Image, output_format: str, target_size: int) -> CompressionResult:
    if output_format == "JPG":
        return _compress_jpg(image, target_size)
    if output_format == "WEBP":
        return _compress_webp(image, target_size)
    if output_format == "PNG":
        return _compress_png(image, target_size)
    return _compress_jpg(image, target_size)


def save_image_to_bytes(image: Image.Image, output_format: str) -> CompressionResult:
    if output_format == "JPG":
        data = _save_to_bytes(_flatten_to_rgb(image), "JPEG", quality=95, optimize=True, progressive=True)
    elif output_format == "WEBP":
        data = _save_to_bytes(_webp_ready(image), "WEBP", quality=95, method=6)
    elif output_format == "PNG":
        data = _save_to_bytes(_png_ready(image), "PNG", optimize=True, compress_level=9)
    else:
        data = _save_to_bytes(_flatten_to_rgb(image), "JPEG", quality=95, optimize=True, progressive=True)

    return CompressionResult(data=data, size=len(data), exceeded=False, detail="saved")


def _compress_jpg(image: Image.Image, target_size: int) -> CompressionResult:
    rgb = _flatten_to_rgb(image)
    last_data = b""
    last_quality = QUALITY_STEPS[-1]

    for quality in QUALITY_STEPS:
        data = _save_to_bytes(
            rgb,
            "JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )
        last_data = data
        last_quality = quality
        if len(data) <= target_size:
            return CompressionResult(data=data, size=len(data), exceeded=False, detail=f"quality={quality}")

    return CompressionResult(
        data=last_data,
        size=len(last_data),
        exceeded=True,
        detail=f"quality={last_quality}",
    )


def _compress_webp(image: Image.Image, target_size: int) -> CompressionResult:
    webp_image = _webp_ready(image)
    last_data = b""
    last_quality = QUALITY_STEPS[-1]

    for quality in QUALITY_STEPS:
        data = _save_to_bytes(webp_image, "WEBP", quality=quality, method=6)
        last_data = data
        last_quality = quality
        if len(data) <= target_size:
            return CompressionResult(data=data, size=len(data), exceeded=False, detail=f"quality={quality}")

    return CompressionResult(
        data=last_data,
        size=len(last_data),
        exceeded=True,
        detail=f"quality={last_quality}",
    )


def _compress_png(image: Image.Image, target_size: int) -> CompressionResult:
    png_image = _png_ready(image)
    best_data = _save_to_bytes(png_image, "PNG", optimize=True, compress_level=9)
    if len(best_data) <= target_size:
        return CompressionResult(data=best_data, size=len(best_data), exceeded=False, detail="compress_level=9")

    palette_mode = Image.Palette.ADAPTIVE if hasattr(Image, "Palette") else Image.ADAPTIVE
    best_detail = "compress_level=9"

    for colors in PNG_PALETTE_COLORS:
        try:
            palette_image = png_image.convert("P", palette=palette_mode, colors=colors)
            data = _save_to_bytes(palette_image, "PNG", optimize=True, compress_level=9)
        except Exception:
            continue

        if len(data) < len(best_data):
            best_data = data
            best_detail = f"palette={colors}"
        if len(data) <= target_size:
            return CompressionResult(data=data, size=len(data), exceeded=False, detail=f"palette={colors}")

    return CompressionResult(data=best_data, size=len(best_data), exceeded=True, detail=best_detail)


def _save_to_bytes(image: Image.Image, file_format: str, **save_kwargs) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=file_format, **save_kwargs)
    return buffer.getvalue()


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if not _has_alpha(image):
        return image.convert("RGB")

    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, "white")
    canvas.paste(rgba, (0, 0), rgba)
    return canvas


def _webp_ready(image: Image.Image) -> Image.Image:
    return image.convert("RGBA") if _has_alpha(image) else image.convert("RGB")


def _png_ready(image: Image.Image) -> Image.Image:
    return image.convert("RGBA") if _has_alpha(image) else image.convert("RGB")
