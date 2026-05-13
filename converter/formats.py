"""Supported image formats and extension metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class ImageFormat:
    key: str
    label: str
    extensions: FrozenSet[str]
    supports_alpha: bool
    is_vector: bool


FORMATS: dict[str, ImageFormat] = {
    "jpg": ImageFormat(
        key="jpg",
        label="JPEG",
        extensions=frozenset({".jpg", ".jpeg"}),
        supports_alpha=False,
        is_vector=False,
    ),
    "png": ImageFormat(
        key="png",
        label="PNG",
        extensions=frozenset({".png"}),
        supports_alpha=True,
        is_vector=False,
    ),
    "webp": ImageFormat(
        key="webp",
        label="WebP",
        extensions=frozenset({".webp"}),
        supports_alpha=True,
        is_vector=False,
    ),
    "heic": ImageFormat(
        key="heic",
        label="HEIC",
        extensions=frozenset({".heic", ".heif"}),
        supports_alpha=True,
        is_vector=False,
    ),
    "svg": ImageFormat(
        key="svg",
        label="SVG",
        extensions=frozenset({".svg"}),
        supports_alpha=True,
        is_vector=True,
    ),
}


EXTENSION_TO_FORMAT: dict[str, str] = {}
for format_key, image_format in FORMATS.items():
    for extension in image_format.extensions:
        EXTENSION_TO_FORMAT[extension.lower()] = format_key


def detect_format(path: str) -> str | None:
    extension = path.rsplit(".", 1)[-1].lower()
    dotted = f".{extension}"
    return EXTENSION_TO_FORMAT.get(dotted)


def format_choices() -> list[tuple[str, str]]:
    return [(image_format.label, image_format.key) for image_format in FORMATS.values()]
