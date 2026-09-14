from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from config import SUPPORTED_EXTENSIONS


MAX_FILENAME_SUFFIX_LENGTH = 64
MAX_FILENAME_COMPONENT_UTF16_UNITS = 255
INVALID_FILENAME_SUFFIX_CHARACTERS = frozenset('<>:"/\\|?*')
DEFAULT_PROCESSED_FILENAME_SUFFIX = "已处理"


def is_supported_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def bytes_to_display(size: int | None) -> str:
    if size is None:
        return "-"

    units = ("B", "KB", "MB", "GB", "TB", "PB")
    value = float(size)
    unit_index = 0
    while abs(value) >= 1_000 and unit_index < len(units) - 1:
        value /= 1_000
        unit_index += 1

    if unit_index == 0:
        return f"{size}B"
    if unit_index == 1:
        text = f"{value:.1f}"
    else:
        text = f"{value:.2f}" if abs(value) < 10 else f"{value:.1f}"
    return f"{text.rstrip('0').rstrip('.')}{units[unit_index]}"


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


def validate_filename_component(filename: str) -> None:
    utf16_units = len(filename.encode("utf-16-le", errors="surrogatepass")) // 2
    if utf16_units > MAX_FILENAME_COMPONENT_UTF16_UNITS:
        raise ValueError("输出文件名过长，请缩短原文件名、LOGO 名称或文件名后缀")


def ensure_unique_path(path: str | Path, reserved: set[str] | None = None) -> Path:
    if reserved is None:
        reserved = set()
    path = Path(path)
    candidate = path
    base_name = path.stem
    suffix = path.suffix
    index = 1

    while True:
        validate_filename_component(candidate.name)
        normalized_candidate = normalize_reserved_path(candidate)
        if not candidate.exists() and normalized_candidate not in reserved:
            break
        candidate = path.with_name(f"{base_name}_{index}{suffix}")
        index += 1

    reserved.add(normalized_candidate)
    return candidate


def normalize_filename_suffix(value: str | None) -> str:
    """Normalize a user-provided filename suffix without its separator."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("文件名后缀必须是文本")

    stripped = value.strip()
    normalized = stripped.lstrip("_").strip()
    if stripped and not normalized:
        raise ValueError("文件名后缀不能只包含下划线")
    if len(normalized) > MAX_FILENAME_SUFFIX_LENGTH:
        raise ValueError(f"文件名后缀不能超过 {MAX_FILENAME_SUFFIX_LENGTH} 个字符")
    if any(
        character in INVALID_FILENAME_SUFFIX_CHARACTERS or ord(character) < 32
        for character in normalized
    ):
        raise ValueError('文件名后缀不能包含 \\ / : * ? " < > |')
    if any(normalized.lower().endswith(extension) for extension in SUPPORTED_EXTENSIONS):
        raise ValueError("文件名后缀无需填写图片扩展名")
    if normalized.endswith("."):
        raise ValueError("文件名后缀不能以句点结尾")
    return normalized


def build_output_file_stem(
    source_path: str | Path,
    suffix_parts: Iterable[str] | None = None,
    custom_suffix: str | None = None,
) -> str:
    source = Path(source_path)
    normalized_custom_suffix = normalize_filename_suffix(custom_suffix)
    if normalized_custom_suffix:
        parts = [normalized_custom_suffix]
    else:
        parts = [part.strip() for part in (suffix_parts or []) if part and part.strip()]
    if parts:
        return f"{source.stem}_{'_'.join(parts)}"
    return f"{source.stem}_{DEFAULT_PROCESSED_FILENAME_SUFFIX}"


def build_default_output_path(
    source_path: str | Path,
    output_directory: str | Path,
    output_choice: str,
    reserved: set[str] | None = None,
    suffix_parts: Iterable[str] | None = None,
    custom_suffix: str | None = None,
) -> Path:
    source = Path(source_path)
    output_format, suffix = resolve_output_format(output_choice, source)
    del output_format
    target = Path(output_directory) / (
        f"{build_output_file_stem(source, suffix_parts, custom_suffix)}{suffix}"
    )
    return ensure_unique_path(target, reserved)


def get_file_size(path: str | Path) -> int:
    return Path(path).stat().st_size
