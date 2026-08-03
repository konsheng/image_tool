from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class LogoAsset:
    name: str
    path: Path

    @property
    def output_name(self) -> str:
        """Return the LOGO name used in generated image filenames."""
        return strip_logo_display_index(self.name)


def strip_logo_display_index(name: str) -> str:
    """Remove a leading two-digit display order from a LOGO asset name."""
    if len(name) <= 2 or not name[:2].isdigit() or name[2].isdigit():
        return name

    output_name = name[2:].lstrip(" ._-")
    return output_name or name


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


def logo_library_path() -> Path:
    return resource_path("assets/logos")


def legacy_logo_path() -> Path:
    return resource_path("assets/logo.png")


def list_logo_assets() -> list[LogoAsset]:
    assets: list[LogoAsset] = []
    library = logo_library_path()

    if library.exists():
        for path in sorted(library.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file() and path.suffix.lower() in LOGO_EXTENSIONS and _can_open_image(path):
                assets.append(LogoAsset(name=path.stem, path=path))

    if assets:
        return assets

    legacy = legacy_logo_path()
    if legacy.exists() and _can_open_image(legacy):
        return [LogoAsset(name=legacy.stem, path=legacy)]

    return []


def load_logo_asset(asset: LogoAsset | str | Path) -> Image.Image:
    path = asset.path if isinstance(asset, LogoAsset) else Path(asset)
    if not path.exists():
        raise FileNotFoundError("内置LOGO加载失败")

    try:
        with Image.open(path) as image:
            return image.convert("RGBA").copy()
    except Exception as exc:
        raise RuntimeError("内置LOGO加载失败") from exc


def load_logo_assets(assets: list[LogoAsset]) -> list[Image.Image]:
    logos = [load_logo_asset(asset) for asset in assets]
    if not logos:
        raise RuntimeError("内置LOGO加载失败")
    return logos


def _can_open_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False
