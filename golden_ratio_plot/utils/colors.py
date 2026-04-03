from __future__ import annotations

import colorsys
import math
from typing import List, Optional, Tuple

PHI_RATIO = 0.6180339887  # 1/φ


def ablation_palette(
    n: int,
    hue: float = 210.0,
    l_start: float = 0.85,
    l_end: float = 0.25,
    saturation: float = 0.65,
) -> List[Tuple[float, float, float]]:
    """Return ``n`` RGB colors that progressively darken with equal lightness steps.

    Linear spacing ensures every pair of adjacent bars has the same lightness
    difference, giving uniform visual separation across the whole legend.

    Parameters
    ----------
    n:
        Number of colors (must be ≥ 1).
    hue:
        HSL hue in degrees [0, 360].  Default 210 (cool blue).
    l_start:
        Lightness of the lightest (first) bar.  0.85 gives a clearly pale tone
        without washing into near-white.
    l_end:
        Lightness of the darkest (last) bar.  0.25 gives a clearly dark tone
        without collapsing into black.
    saturation:
        HSL saturation, constant across all bars.

    Returns
    -------
    List of ``(r, g, b)`` tuples with values in [0, 1].
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    if n == 1:
        return [_hsl_to_rgb(hue, saturation, (l_start + l_end) / 2)]

    lightness_values = [
        l_start - i * (l_start - l_end) / (n - 1)
        for i in range(n)
    ]
    lightness_values = [max(0.05, min(0.95, l)) for l in lightness_values]
    return [_hsl_to_rgb(hue, saturation, l) for l in lightness_values]


def _hsl_to_rgb(
    hue_deg: float,
    saturation: float,
    lightness: float,
) -> Tuple[float, float, float]:
    """Convert HSL (hue in degrees) to RGB (values in [0, 1])."""
    h = (hue_deg % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(h, lightness, saturation)
    return (r, g, b)


def palette_from_config(
    n: int,
    custom: Optional[List[str]],
    hue: float,
) -> List[Tuple[float, float, float]]:
    """Return a palette of ``n`` RGB colors.

    Uses ``custom`` list (hex strings) if provided and long enough; otherwise
    falls back to :func:`ablation_palette`.
    """
    if custom and len(custom) >= n:
        return [_hex_to_rgb(c) for c in custom[:n]]
    if custom and len(custom) > 0:
        # Custom list is too short — extend with auto-generated colors.
        base = [_hex_to_rgb(c) for c in custom]
        extra = ablation_palette(n - len(base), hue=hue)
        return base + extra
    return ablation_palette(n, hue=hue)


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Parse a hex color string (#RRGGBB or RRGGBB) into (r, g, b) ∈ [0,1]."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_color!r}")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)
