from __future__ import annotations

import colorsys
import math
from typing import List, Optional, Tuple

PHI_RATIO = 0.6180339887  # 1/φ


def ablation_palette(
    n: int,
    hue: float = 210.0,
    l_start: float = 0.72,
    l_end: float = 0.32,
    saturation: float = 0.60,
) -> List[Tuple[float, float, float]]:
    """Return ``n`` RGB colors that progressively darken using a φ-based step.

    The lightness differences between consecutive bars follow a geometric series
    with ratio ``0.618``, so early bars are close in shade and the final bar
    anchors the darkest end.  This avoids the "last bar too black" problem of
    linear spacing while still providing clear visual distinction.

    Parameters
    ----------
    n:
        Number of colors (must be ≥ 1).
    hue:
        HSL hue in degrees [0, 360].  Default 210 (cool blue).
    l_start:
        Lightness of the lightest (first) bar.
    l_end:
        Lightness of the darkest (last) bar.
    saturation:
        HSL saturation, constant across all bars.

    Returns
    -------
    List of ``(r, g, b)`` tuples with values in [0, 1].
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    if n == 1:
        l_mid = (l_start + l_end) / 2
        return [_hsl_to_rgb(hue, saturation, l_mid)]

    lightness_values = _geometric_lightness(n, l_start, l_end)
    return [_hsl_to_rgb(hue, saturation, l) for l in lightness_values]


def _geometric_lightness(
    n: int,
    l_start: float,
    l_end: float,
) -> List[float]:
    """Build lightness values with φ-ratio geometric step sizes.

    Step sizes satisfy:  Δ_i = base_step × φ_ratio^(n-1-i)
    so the largest single step is at the end (i → n-1), and steps shrink
    going backwards.  Total span = l_start − l_end.
    """
    total = l_start - l_end
    # Sum of geometric series: base_step × (1 - r^n) / (1 - r)
    # Solve for base_step given the total.
    r = PHI_RATIO
    if abs(r - 1.0) < 1e-12 or n == 1:
        base_step = total / (n - 1) if n > 1 else total
    else:
        geo_sum = (1.0 - r ** n) / (1.0 - r)
        base_step = total / geo_sum

    lightness: List[float] = [l_start]
    for i in range(n - 1):
        step = base_step * (r ** (n - 2 - i))
        lightness.append(lightness[-1] - step)

    # Clamp to valid range
    return [max(0.05, min(0.95, l)) for l in lightness]


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
