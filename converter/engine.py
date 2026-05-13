"""High-fidelity image conversion between raster and vector formats."""

from __future__ import annotations

import base64
import io
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from .formats import FORMATS, detect_format

ProgressCallback = Callable[[int, int, str], None]

_heif_opener_registered = False


def ensure_heif_opener() -> None:
    global _heif_opener_registered
    if _heif_opener_registered:
        return
    try:
        from pillow_heif import register_heif_opener
    except ImportError as exc:
        raise RuntimeError(
            "pillow-heif is required for HEIC/HEIF. Install dependencies from requirements.txt."
        ) from exc
    register_heif_opener()
    _heif_opener_registered = True


@dataclass(frozen=True)
class ConversionOptions:
    target_format: str
    output_dir: Path
    width: int | None = None
    height: int | None = None
    preserve_aspect_ratio: bool = True


@dataclass(frozen=True)
class ConversionResult:
    source: Path
    destination: Path
    success: bool
    message: str = ""


def collect_image_paths(paths: list[str]) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()

    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and detect_format(child.name):
                    resolved = child.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        collected.append(resolved)
            continue

        if path.is_file() and detect_format(path.name):
            if path not in seen:
                seen.add(path)
                collected.append(path)

    return collected


def convert_batch(
    sources: list[Path],
    options: ConversionOptions,
    progress: ProgressCallback | None = None,
) -> list[ConversionResult]:
    results: list[ConversionResult] = []
    total = len(sources)

    options.output_dir.mkdir(parents=True, exist_ok=True)

    for index, source in enumerate(sources, start=1):
        if progress:
            progress(index - 1, total, source.name)

        try:
            destination = convert_single(source, options)
            results.append(
                ConversionResult(
                    source=source,
                    destination=destination,
                    success=True,
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in GUI log
            results.append(
                ConversionResult(
                    source=source,
                    destination=options.output_dir / build_output_name(source, options.target_format),
                    success=False,
                    message=str(exc),
                )
            )

        if progress:
            progress(index, total, source.name)

    return results


def convert_single(source: Path, options: ConversionOptions) -> Path:
    source_format = detect_format(source.name)
    if not source_format:
        raise ValueError(f"Unsupported source format: {source.name}")

    if options.target_format not in FORMATS:
        raise ValueError(f"Unsupported target format: {options.target_format}")

    destination = options.output_dir / build_output_name(source, options.target_format)

    if source_format == "svg" and options.target_format == "svg":
        write_svg_to_svg(source, destination, options)
        return destination

    if source_format == "svg":
        image = load_svg_as_raster(source, options)
        save_raster(image, destination, options.target_format)
        return destination

    if source_format == "heic" or options.target_format == "heic":
        ensure_heif_opener()

    image = Image.open(source)
    image.load()

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    image = apply_resize(image, options)

    if options.target_format == "svg":
        write_raster_as_svg(image, destination)
        return destination

    save_raster(image, destination, options.target_format)
    return destination


def build_output_name(source: Path, target_format: str) -> str:
    target = FORMATS[target_format]
    extension = sorted(target.extensions)[0]
    return f"{source.stem}{extension}"


def apply_resize(image: Image.Image, options: ConversionOptions) -> Image.Image:
    if options.width is None and options.height is None:
        return image

    original_width, original_height = image.size

    if options.width is not None and options.height is not None:
        target_size = (options.width, options.height)
    elif options.width is not None:
        if options.preserve_aspect_ratio:
            ratio = options.width / original_width
            target_size = (options.width, max(1, round(original_height * ratio)))
        else:
            target_size = (options.width, original_height)
    else:
        if options.preserve_aspect_ratio:
            ratio = options.height / original_height
            target_size = (max(1, round(original_width * ratio)), options.height)
        else:
            target_size = (original_width, options.height)

    if target_size == image.size:
        return image

    return image.resize(target_size, Image.Resampling.LANCZOS)


def load_svg_as_raster(source: Path, options: ConversionOptions) -> Image.Image:
    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError(
            "cairosvg is required for SVG input. Install dependencies from requirements.txt."
        ) from exc

    if options.width is not None and options.height is not None:
        output_width, output_height = options.width, options.height
    elif options.width is not None or options.height is not None:
        base_width, base_height = read_svg_intrinsic_size(source)
        output_width, output_height = apply_resize(
            Image.new("RGBA", (base_width, base_height)),
            options,
        ).size
    else:
        output_width, output_height = read_svg_intrinsic_size(source)

    png_bytes = cairosvg.svg2png(
        url=str(source),
        output_width=output_width,
        output_height=output_height,
    )
    image = Image.open(io.BytesIO(png_bytes))
    image.load()
    return image.convert("RGBA")


def read_svg_intrinsic_size(source: Path) -> tuple[int, int]:
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Invalid SVG file: {source.name}") from exc

    width = parse_svg_length(root.get("width"))
    height = parse_svg_length(root.get("height"))

    if width and height:
        return max(1, round(width)), max(1, round(height))

    view_box = root.get("viewBox")
    if view_box:
        parts = re.split(r"[\s,]+", view_box.strip())
        if len(parts) == 4:
            return max(1, round(float(parts[2]))), max(1, round(float(parts[3])))

    return 1024, 1024


def parse_svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"^([\d.]+)", value.strip())
    if not match:
        return None
    return float(match.group(1))


def write_svg_to_svg(source: Path, destination: Path, options: ConversionOptions) -> None:
    svg_text = source.read_text(encoding="utf-8")
    if options.width is None and options.height is None:
        destination.write_text(svg_text, encoding="utf-8")
        return

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid SVG file: {source.name}") from exc

    current_width, current_height = read_svg_intrinsic_size(source)
    resized = apply_resize(
        Image.new("RGBA", (current_width, current_height)),
        options,
    )
    target_width, target_height = resized.size

    root.set("width", str(target_width))
    root.set("height", str(target_height))
    if root.get("viewBox") is None:
        root.set("viewBox", f"0 0 {current_width} {current_height}")

    destination.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def write_raster_as_svg(image: Image.Image, destination: Path) -> None:
    rgba = image.convert("RGBA")
    buffer = io.BytesIO()
    rgba.save(buffer, format="PNG", compress_level=6)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    width, height = rgba.size

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'  <image width="{width}" height="{height}" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'xlink:href="data:image/png;base64,{encoded}"/>\n'
        "</svg>\n"
    )
    destination.write_text(svg, encoding="utf-8")


def save_raster(image: Image.Image, destination: Path, target_format: str) -> None:
    target = FORMATS[target_format]

    if target.supports_alpha:
        output = image.convert("RGBA")
    else:
        output = flatten_alpha(image)

    save_kwargs: dict[str, object] = {}

    if target_format == "jpg":
        save_kwargs.update(
            {
                "format": "JPEG",
                "quality": 95,
                "subsampling": 0,
                "optimize": True,
            }
        )
    elif target_format == "png":
        save_kwargs.update(
            {
                "format": "PNG",
                "compress_level": 6,
            }
        )
    elif target_format == "webp":
        has_alpha = "A" in output.getbands() and output.getchannel("A").getextrema()[1] < 255
        save_kwargs.update(
            {
                "format": "WEBP",
                "lossless": has_alpha,
                "quality": 95,
                "method": 6,
            }
        )
    elif target_format == "heic":
        ensure_heif_opener()
        save_kwargs.update(
            {
                "format": "HEIF",
                "quality": 90,
            }
        )
    else:
        raise ValueError(f"Unsupported raster target: {target_format}")

    output.save(destination, **save_kwargs)


def flatten_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")
