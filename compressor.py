from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from config import DEFAULT_MANUAL_QUALITY, MAX_MANUAL_QUALITY, MIN_MANUAL_QUALITY


@dataclass(frozen=True)
class CompressionResult:
    data: bytes
    size: int
    detail: str
    quality: int | None = None


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
            detail="compress_level=9",
            quality=None,
        )
    else:
        effective_quality = _validated_quality(quality)
        data = _encode_jpg(_flatten_to_rgb(image), effective_quality)

    return CompressionResult(
        data=data,
        size=len(data),
        detail=f"quality={effective_quality}",
        quality=effective_quality,
    )


def _validated_quality(quality: int | None) -> int:
    if quality is None:
        return DEFAULT_MANUAL_QUALITY
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
