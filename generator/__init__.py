"""Excel and PDF report generation modules."""

import colorsys
import random
from typing import Any, Optional

COLUMNS = [
    "Sr. no.",
    "Product Name",
    "Total Price",
    "Less Price",
    "Real Price",
    "Size",
    "Type",
]


def _relative_luminance(r: float, g: float, b: float) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pick_random_header_color() -> str:
    """Pick a random vibrant background hex color with enough luminance for black bold text."""
    for _ in range(25):
        hue = random.uniform(0.0, 1.0)
        saturation = random.uniform(0.55, 0.90)
        lightness = random.uniform(0.58, 0.78)
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        if _relative_luminance(r, g, b) >= 0.36:
            return f"#{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"
    return "#4ADE80"


def resolve_header_color(settings: dict[str, Any], override_hex: Optional[str] = None) -> str:
    """Return an explicit header color, a random readable color, or configured fallback."""
    if override_hex:
        cleaned = override_hex.strip().lstrip("#")
        return f"#{cleaned.upper()}"
    out_cfg = settings.get("output", {})
    if out_cfg.get("randomize_header_color", True):
        return pick_random_header_color()
    fallback = str(out_cfg.get("header_bg_color", "#18B500")).strip().lstrip("#")
    return f"#{fallback.upper()}"
