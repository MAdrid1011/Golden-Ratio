from __future__ import annotations

import math
from typing import List


def nice_ticks(
    data_min: float,
    data_max: float,
    n: int = 5,
) -> List[float]:
    """Return approximately ``n`` evenly-spaced "nice" tick values.

    The algorithm selects a step size from the series {1, 2, 5} × 10^k that
    produces the requested number of ticks and prefers integer values when the
    data range allows.

    Parameters
    ----------
    data_min:
        Lower bound of the data (or user-supplied ``y_min``).
    data_max:
        Upper bound of the data (or user-supplied ``y_max``).
    n:
        Target number of ticks (default 5).

    Returns
    -------
    List[float]
        Sorted tick values that span from ``≤ data_min`` to ``≥ data_max``.
    """
    if data_min == data_max:
        # Degenerate: return a symmetric range of n ticks around the value.
        step = max(abs(data_min) * 0.1, 1.0)
        start = data_min - step * (n // 2)
        return [start + step * i for i in range(n)]

    raw_step = (data_max - data_min) / max(n - 1, 1)
    nice_step = _nice_number(raw_step, round_up=False)

    tick_min = math.floor(data_min / nice_step) * nice_step
    tick_max = math.ceil(data_max / nice_step) * nice_step

    ticks: List[float] = []
    t = tick_min
    while t <= tick_max + nice_step * 1e-9:
        ticks.append(_clean(t))
        t += nice_step

    return ticks


def nice_range(
    data_min: float,
    data_max: float,
    n: int = 5,
    top_padding_intervals: float = 0.618,
) -> tuple[float, float, List[float]]:
    """Return ``(axis_min, axis_max, ticks)`` with a golden-ratio top padding.

    ``axis_max`` is set to ``data_max + top_padding_intervals × tick_step``.
    Any tick that lies above ``axis_max`` is dropped so the space above the
    tallest bar stays minimal.  The previous behaviour of padding above the
    last nice tick caused excessive dead space when the last tick was already
    well above data_max.

    Parameters
    ----------
    top_padding_intervals:
        Fraction of one tick interval added above ``data_max``.
        Default is ``0.618`` (golden ratio).
    """
    ticks = nice_ticks(data_min, data_max, n)
    tick_step = ticks[1] - ticks[0] if len(ticks) >= 2 else 1.0
    axis_min = ticks[0]
    axis_max = data_max + tick_step * top_padding_intervals
    # Keep only ticks that fall within the visible range.
    ticks = [t for t in ticks if t <= axis_max + tick_step * 1e-9]
    return axis_min, axis_max, ticks


# ── Internal helpers ──────────────────────────────────────────────────────────

def _nice_number(value: float, round_up: bool = False) -> float:
    """Round ``value`` to the nearest nice number {1, 2, 5} × 10^k."""
    exp = math.floor(math.log10(value))
    frac = value / (10 ** exp)

    if round_up:
        if frac <= 1:
            nice = 1
        elif frac <= 2:
            nice = 2
        elif frac <= 5:
            nice = 5
        else:
            nice = 10
    else:
        if frac < 1.5:
            nice = 1
        elif frac < 3.5:
            nice = 2
        elif frac < 7.5:
            nice = 5
        else:
            nice = 10

    return nice * (10 ** exp)


def _clean(value: float) -> float:
    """Remove floating-point noise from a value near an integer or simple decimal."""
    rounded = round(value, 10)
    if abs(rounded - round(rounded)) < 1e-9:
        return float(round(rounded))
    return rounded
