"""Shared x-axis label utilities used by all renderer modules.

Constants
---------
AXES_WIDTH_FRACTION  — fraction of figure width occupied by the axes area

Functions
---------
vcenter_xticklabels  — vertically centre single-line labels within multi-line rows
"""

from __future__ import annotations

from matplotlib.axes import Axes

# Fraction of figure width used for the axes area (the rest is margins,
# tick labels, and axis titles).  Consistent across ablation and decomp.
AXES_WIDTH_FRACTION: float = 0.82


def vcenter_xticklabels(ax: Axes, font_size: float) -> None:
    """Vertically centre short x-tick labels within the tallest label's space.

    When some group names wrap to two lines and others fit on one line, the
    one-line labels sit at the *top* of the allocated text cell, leaving a
    blank gap below them.  This function adds half a line-height of tick pad
    to shorter labels so they appear centred.

    The adjustment is applied via ``Tick.set_pad()`` which survives subsequent
    ``canvas.draw()`` calls (unlike Affine transforms on Text objects, which
    the tick machinery resets).

    Parameters
    ----------
    ax:         The axes whose x-tick labels to adjust.
    font_size:  Font size in points of the x-tick labels.
    """
    line_h_pt   = font_size * 1.25  # approximate line height (1.25× leading)
    tick_lbls   = ax.get_xticklabels()
    major_ticks = ax.xaxis.get_major_ticks()
    if not tick_lbls or not major_ticks:
        return

    max_nl = max(
        sum(1 for ln in lbl.get_text().split("\n") if ln.strip())
        for lbl in tick_lbls
    )
    for tick, lbl in zip(major_ticks, tick_lbls):
        nl = sum(1 for ln in lbl.get_text().split("\n") if ln.strip())
        if nl < max_nl:
            tick.set_pad(tick.get_pad() + (max_nl - nl) * line_h_pt / 2.0)
