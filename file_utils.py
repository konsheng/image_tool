from __future__ import annotations

import os
from pathlib import Path

from config import SUPPORTED_EXTENSIONS


def is_supported_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def bytes_to_display(size: int | None) -> str:
    if size is None:
        return "-"
    if size >= 1_000_000:
        value = size / 1_000_000
        text = f"{value:.2f}" if value < 10 else f"{value:.1f}"
        return f"{text.rstrip('0').rstrip('.')}MB"
    if size >= 1_000:
        value = size / 1_000
        text = f"{value:.1f}"
        return f"{text.rstrip('0').rstrip('.')}KB"
    return f"{size}B"


def format_dimensions(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "-"
    return f"{width}×{height}"


def normalize_reserved_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def resolve_output_format(output_choice: str, source_path: str | Path) -> tuple[str, str]:
    if output_choice == "保持原格式":
        suffix = Path(source_path).suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "JPG", ".jpg"
        if suffix == ".png":
            return "PNG", ".png"
        if suffix == ".webp":
            return "WEBP", ".webp"
        return "JPG", ".jpg"

    normalized = output_choice.upper()
    if normalized == "JPG":
        return "JPG", ".jpg"
    if normalized == "PNG":
        return "PNG", ".png"
    if normalized == "WEBP":
        return "WEBP", ".webp"
    return "JPG", ".jpg"


def ensure_suffix(path: Path, suffix: str) -> Path:
    if path.suffix.lower() != suffix.lower():
        return path.with_suffix(suffix)
    return path


def ensure_unique_path(path: str | Path, reserved: set[str] | None = None) -> Path:
    reserved = reserved or set()
    path = Path(path)
    candidate = path
    base_name = path.stem
    suffix = path.suffix
    index = 1

    while candidate.exists() or normalize_reserved_path(candidate) in reserved:
        candidate = path.with_name(f"{base_name}_{index}{suffix}")
        index += 1

    reserved.add(normalize_reserved_path(candidate))
    return candidate


def build_default_output_path(
    source_path: str | Path,
    output_directory: str | Path,
    output_choice: str,
    reserved: set[str] | None = None,
) -> Path:
    source = Path(source_path)
    output_format, suffix = resolve_output_format(output_choice, source)
    del output_format
    target = Path(output_directory) / f"{source.stem}_已处理{suffix}"
    return ensure_unique_path(target, reserved)


def get_file_size(path: str | Path) -> int:
    return Path(path).stat().st_size
