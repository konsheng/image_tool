from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Callable

from PIL import Image

from config import MAX_MANUAL_QUALITY, MIN_MANUAL_QUALITY, PNG_PALETTE_COLORS


TARGET_QUALITY_MIN = 1
TARGET_QUALITY_MAX = 95


@dataclass(frozen=True)
class CompressionResult:
    data: bytes
    size: int
    exceeded: bool
    detail: str
    quality: int | None = None


def compress_image_to_bytes(image: Image.Image, output_format: str, target_size: int) -> CompressionResult:
    if output_format == "JPG":
        return _compress_jpg(image, target_size)
    if output_format == "WEBP":
        return _compress_webp(image, target_size)
    if output_format == "PNG":
        return _compress_png(image, target_size)
    return _compress_jpg(image, target_size)


def save_image_to_bytes(
    image: Image.Image,
    output_format: str,
    quality: int | None = None,
) -> CompressionResult:
    if output_format == "JPG":
        effective_quality = _validated_quality(quality)
        data = _encode_jpg(_flatten_to_rgb(image), effective_quality)
    elif output_format == "WEBP":
        effective_quality = _validated_quality(quality)
        data = _encode_webp(_webp_ready(image), effective_quality)
    elif output_format == "PNG":
        data = _save_to_bytes(_png_ready(image), "PNG", optimize=True, compress_level=9)
        return CompressionResult(
            data=data,
            size=len(data),
            exceeded=False,
            detail="compress_level=9",
            quality=None,
        )
    else:
        effective_quality = _validated_quality(quality)
        data = _encode_jpg(_flatten_to_rgb(image), effective_quality)

    return CompressionResult(
        data=data,
        size=len(data),
        exceeded=False,
        detail=f"quality={effective_quality}",
        quality=effective_quality,
    )


def _compress_jpg(image: Image.Image, target_size: int) -> CompressionResult:
    rgb = _flatten_to_rgb(image)
    return _compress_lossy_to_target(
        lambda quality: _encode_jpg(rgb, quality),
        target_size,
    )


def _compress_webp(image: Image.Image, target_size: int) -> CompressionResult:
    webp_image = _webp_ready(image)
    return _compress_lossy_to_target(
        lambda quality: _encode_webp(webp_image, quality),
        target_size,
    )


def _compress_lossy_to_target(
    encoder: Callable[[int], bytes],
    target_size: int,
) -> CompressionResult:
    """Return the globally highest quality whose encoded bytes fit the target."""
    smallest_data: bytes | None = None
    smallest_quality = TARGET_QUALITY_MIN

    # Encoded size is not guaranteed to increase monotonically with quality,
    # especially for simple WebP/JPEG images.  Descending exhaustive search is
    # therefore required to make the highest-quality guarantee exact.
    for quality in range(TARGET_QUALITY_MAX, TARGET_QUALITY_MIN - 1, -1):
        data = encoder(quality)
        if smallest_data is None or len(data) < len(smallest_data):
            smallest_data = data
            smallest_quality = quality
        if len(data) <= target_size:
            return _lossy_result(data, quality, exceeded=False)

    assert smallest_data is not None
    return _lossy_result(smallest_data, smallest_quality, exceeded=True)


def _lossy_result(data: bytes, quality: int, *, exceeded: bool) -> CompressionResult:
    return CompressionResult(
        data=data,
        size=len(data),
        exceeded=exceeded,
        detail=f"quality={quality}",
        quality=quality,
    )


def _compress_png(image: Image.Image, target_size: int) -> CompressionResult:
    png_image = _png_ready(image)
    best_data = _save_to_bytes(png_image, "PNG", optimize=True, compress_level=9)
    if len(best_data) <= target_size:
        return CompressionResult(
            data=best_data,
            size=len(best_data),
            exceeded=False,
            detail="compress_level=9",
            quality=None,
        )

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
            return CompressionResult(
                data=data,
                size=len(data),
                exceeded=False,
                detail=f"palette={colors}",
                quality=None,
            )

    return CompressionResult(
        data=best_data,
        size=len(best_data),
        exceeded=True,
        detail=best_detail,
        quality=None,
    )


def _validated_quality(quality: int | None) -> int:
    if quality is None:
        return TARGET_QUALITY_MAX
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise ValueError("quality must be an integer")
    if not MIN_MANUAL_QUALITY <= quality <= MAX_MANUAL_QUALITY:
        raise ValueError(
            f"quality must be between {MIN_MANUAL_QUALITY} and {MAX_MANUAL_QUALITY}"
        )
    return quality


def _encode_jpg(image: Image.Image, quality: int) -> bytes:
    return _save_to_bytes(
        image,
        "JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )


def _encode_webp(image: Image.Image, quality: int) -> bytes:
    return _save_to_bytes(image, "WEBP", quality=quality, method=6)


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
