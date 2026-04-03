"""Sensitivity-study renderer — grid of dual-axis line charts.

Layout rules
------------
- n ≤ 4        → one row of n panels.
- n > 4, n%3=0 → ceil(n/3) rows × 3 columns  (preferred).
- n > 4, n%2=0 → ceil(n/2) rows × 2 columns.
- otherwise    → ValueError.

Each panel cell has aspect ratio φ:1 (width:height).  Total figure width is
always ``cfg.width_pt`` (default 240 pt).

Axis conventions
----------------
- Left  y-axis: red  tick labels, red  spine, red  axis label.
- Right y-axis: blue tick labels, blue spine, blue axis label.
- Bottom x-axis: black, no label.  Top spine: hidden.
- Both y-axes share the same number of ticks; tick padding is identical on
  both sides so every tick sits at the same fractional height → gridlines
  at left-tick positions coincide exactly with right-tick positions.
- Horizontal gray dashed gridlines at every left tick level (zorder=0).

Legend
------
Only shown when a panel has more than one group.  Each legend entry shows a
short connector line (in the group's line style, dark gray) flanked by a red
circle (left axis) and a blue circle (right axis).

Line styles cycle: solid → dashed → dotted (max 3 groups per panel).
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as _mticker
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.path import Path as _MPath
from golden_ratio_plot.config import PHI, PT_PER_INCH, PlotConfig
from golden_ratio_plot.reader import SensitivityData
from golden_ratio_plot.renderer.base import BaseRenderer

# ── Constants ─────────────────────────────────────────────────────────────────

_LEFT_COLOR  = "#EE3311"   # vivid vermilion red
_RIGHT_COLOR = "#0099DD"   # vivid sky blue
_GRID_COLOR  = "#aaaaaa"
_GRID_ALPHA  = 0.75
_GRID_LW     = 0.5

# Line styles for distinguishing multiple groups (max 3).
_LINE_STYLES: List[str] = ["-", "--", ":"]

# Narrow vertical rectangle used as the interpolated-point marker.
# Coordinates are in marker units (scaled by markersize).
# Square marker: width = height = ±0.08 (in normalized marker coordinates)
_RECT_MARKER = _MPath(
    [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5)],
    [_MPath.MOVETO, _MPath.LINETO, _MPath.LINETO, _MPath.LINETO, _MPath.CLOSEPOLY],
)

# Fraction of one tick-step added as padding above and below the tick range.
# No padding: the outermost ticks sit exactly at the axis boundaries so that
# gridlines touch both the top and bottom edges of every panel.
_Y_PAD = 0.0


# ── Grid layout ───────────────────────────────────────────────────────────────

def _determine_grid(n: int) -> Tuple[int, int]:
    """Return (n_cols, n_rows) for *n* sensitivity panels.

    Raises
    ------
    ValueError
        If n > 4 and is neither divisible by 3 nor by 2.
    """
    if n <= 0:
        raise ValueError("Need at least one panel.")
    if n <= 4:
        return n, 1
    if n % 3 == 0:
        return 3, n // 3
    if n % 2 == 0:
        return 2, n // 2
    raise ValueError(
        f"{n} panels: cannot arrange in a grid. "
        "For n > 4, n must be divisible by 3 (preferred) or by 2."
    )


# ── Scale helpers ─────────────────────────────────────────────────────────────

def _nice_step(rough: float) -> float:
    """Round *rough* step UP to the nearest {1, 2, 2.5, 5} × 10^n."""
    if rough <= 0:
        return 1.0
    exp = math.floor(math.log10(rough))
    frac = rough / (10.0 ** exp)
    if frac <= 1.0:
        nice = 1.0
    elif frac <= 2.0:
        nice = 2.0
    elif frac <= 2.5:
        nice = 2.5
    elif frac <= 5.0:
        nice = 5.0
    else:
        nice = 1.0
        exp += 1
    return nice * (10.0 ** exp)


def _axis_scale(
    values: List[float],
    n_target: int = 6,
    stable: bool = False,
) -> Tuple[float, float, List[float], float]:
    """Return *(y_min, y_max, ticks, step)* with exactly *n_target* ticks.

    Boundaries are snapped **outward** to the order-of-magnitude of the data
    span (e.g. span 0.13 → round to nearest 0.1; span 19 → nearest 10).
    The step is then ``(nice_max − nice_min) / (n_target − 1)``, which
    divides exactly with no over-stretching.  Axis limits equal the first and
    last tick (no extra padding) so gridlines touch both edges.

    When *stable* is ``True`` the effective span is widened to 10× the actual
    data span (centred on the data midpoint), making tiny variations appear as
    a nearly-flat line — visually demonstrating the metric's stability.
    """
    d_min, d_max = min(values), max(values)
    data_span = d_max - d_min

    if stable and data_span > 1e-12:
        d_center = (d_min + d_max) / 2.0
        expanded = data_span * 10.0
        d_min = d_center - expanded / 2.0
        d_max = d_center + expanded / 2.0
        data_span = expanded

    if data_span < 1e-12:
        mag = abs(d_min) if abs(d_min) > 1e-12 else 1.0
        scale = _nice_step(mag / max(n_target - 1, 1))
        nice_min = math.floor(d_min / scale) * scale
        nice_max = round(nice_min + (n_target - 1) * scale, 12)
    else:
        # Use _nice_step of the per-interval span as the rounding scale.
        # This is finer than 10^floor(log10(span)) when span/(n-1) falls
        # below a power-of-10 boundary (e.g. 19/5=3.8 → scale=5, not 10).
        scale = _nice_step(data_span / max(n_target - 1, 1))
        nice_min = math.floor(d_min / scale) * scale
        nice_max = math.ceil( d_max / scale) * scale

    step = (nice_max - nice_min) / (n_target - 1)
    ticks = [round(nice_min + i * step, 12) for i in range(n_target)]
    return ticks[0], ticks[-1], ticks, step


def _aligned_scales(
    left_vals: List[float],
    right_vals: List[float],
    n_target: int = 6,
    left_stable: bool = False,
    right_stable: bool = False,
) -> Tuple[float, float, List[float], float, float, List[float]]:
    """Return aligned y-scales: exactly *n_target* ticks on each axis.

    Because :func:`_axis_scale` always produces exactly *n_target* ticks,
    both axes are guaranteed to align — no search or fallback required.
    """
    l_min, l_max, l_ticks, _ = _axis_scale(left_vals,  n_target, stable=left_stable)
    r_min, r_max, r_ticks, _ = _axis_scale(right_vals, n_target, stable=right_stable)
    return l_min, l_max, l_ticks, r_min, r_max, r_ticks


def _decimal_places(step: float) -> int:
    """Decimal places needed to display *step* without trailing zeros."""
    if step >= 1.0 or step <= 0.0:
        return 0
    return max(0, -int(math.floor(math.log10(abs(step)))))


# ── Interpolation helper ──────────────────────────────────────────────────────

def _interp_jitter(
    y: List[float],
    n_between: int,
    noise_frac: float = 0.018,
    seed: int = 0,
) -> Tuple[List[float], List[float]]:
    """Return *(x_dense, y_dense)* via Catmull-Rom spline + smooth jitter.

    Parameters
    ----------
    y          : original y values at integer x positions 0, 1, …, n-1.
    n_between  : extra points inserted between each consecutive pair.
    noise_frac : jitter amplitude as a fraction of the data span.
    seed       : RNG seed — deterministic per data series.
    """
    n = len(y)
    if n < 2 or n_between < 1:
        return list(range(n)), list(y)

    total = (n - 1) * n_between + 1
    # Dense x positions: 0 … n-1 in fractional steps of 1/n_between
    x_dense = [i / n_between for i in range(total)]

    # Catmull-Rom spline through original points
    y_spline: List[float] = []
    for xi in x_dense:
        i = min(int(xi), n - 2)
        t = xi - i
        p0 = y[max(i - 1, 0)]
        p1 = y[i]
        p2 = y[min(i + 1, n - 1)]
        p3 = y[min(i + 2, n - 1)]
        val = 0.5 * (
            2.0 * p1
            + (-p0 + p2) * t
            + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t ** 2
            + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t ** 3
        )
        y_spline.append(val)

    # Smooth, band-limited jitter — amplitude proportional to data span
    data_span = max(y) - min(y)
    if data_span < 1e-12:
        data_span = abs(y[0]) * 0.01 if abs(y[0]) > 1e-12 else 1e-3

    rng = np.random.RandomState(seed % (2 ** 31))
    raw = rng.randn(total)
    # Moving-average smoothing so jitter is correlated (not white noise)
    k = max(3, n_between // 2)
    kernel = np.ones(k) / k
    smooth = np.convolve(raw, kernel, mode="same")
    std = float(smooth.std()) or 1.0
    smooth = smooth / std * noise_frac * data_span

    # Pin jitter to zero at original data positions so the curve passes exactly
    # through those points (indices 0, n_between, 2·n_between, …).
    for i in range(n):
        smooth[i * n_between] = 0.0

    y_raw = [ys + ns for ys, ns in zip(y_spline, smooth.tolist())]

    # Clamp only the strictly interpolated positions (non-original) so that
    # every in-between point stays noticeably inside [y_lo, y_hi].
    # Original positions (indices 0, n_between, 2·n_between, …) are restored
    # to their exact data values so the line passes through every circle.
    y_lo, y_hi = min(y), max(y)
    span = y_hi - y_lo
    # Interpolated points must stay strictly inside (y_lo, y_hi) but as close
    # as needed — just never equal to the extremes.
    eps = span * 1e-6 if span > 0 else 1e-9
    y_dense = []
    for idx, v in enumerate(y_raw):
        orig_idx, rem = divmod(idx, n_between)
        if rem == 0:  # original data position — use exact value
            y_dense.append(y[orig_idx])
        else:
            y_dense.append(max(y_lo + eps, min(y_hi - eps, v)))
    return x_dense, y_dense


# ── Panel drawing ─────────────────────────────────────────────────────────────

def _draw_panel(
    fig: Figure, ax: Axes, data: SensitivityData, cfg: PlotConfig, n_cols: int = 1
) -> None:
    """Populate one sensitivity subplot."""
    fs = cfg.font_size_pt
    # Tick length scales linearly with panel width (∝ 1/n_cols).
    tick_len = max(1.0, 3.0 / n_cols)

    # ── X positions (categorical, evenly spaced) ──────────────────────────────
    n_x = len(data.x_values)
    x_pos = list(range(n_x))

    # ── Right y-axis (twin) ───────────────────────────────────────────────────
    # ax owns left / top / bottom spines; ax2 owns only the right spine.
    # All spines and tick marks are BLACK; only labels and axis titles carry colour.
    ax2 = ax.twinx()
    for s in ("top", "left", "bottom"):
        ax2.spines[s].set_visible(False)
    ax2.spines["right"].set_linewidth(cfg.spine_linewidth_pt)
    ax2.spines["right"].set_color("black")   # spine is black
    ax2.spines["right"].set_clip_on(False)
    ax2.tick_params(
        axis="y",
        which="both",
        direction="out",
        width=cfg.spine_linewidth_pt,
        length=tick_len,
        pad=1.0,                    # tight gap between tick mark and label
        right=True,
        left=False,
        colors="black",             # tick marks: black
        labelcolor=_RIGHT_COLOR,    # tick label numbers: blue
        labelsize=fs,
    )
    ax2.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

    # ── Left / top / bottom spines (all black, all visible) ───────────────────
    lw = cfg.spine_linewidth_pt
    ax.spines["left"].set_color("black")    # spine black
    ax.spines["left"].set_linewidth(lw)
    ax.spines["left"].set_clip_on(False)
    ax.spines["top"].set_color("black")     # top border: visible and black
    ax.spines["top"].set_linewidth(lw)
    ax.spines["top"].set_clip_on(False)
    ax.spines["bottom"].set_color("black")
    ax.spines["bottom"].set_linewidth(lw)
    ax.spines["bottom"].set_clip_on(False)
    ax.spines["right"].set_visible(False)   # ax2 draws the right spine
    ax.tick_params(
        axis="y",
        which="both",
        direction="out",
        width=lw,
        length=tick_len,
        pad=1.0,                    # tight gap between tick mark and label
        left=True,
        right=False,
        colors="black",             # tick marks: black
        labelcolor=_LEFT_COLOR,     # tick label numbers: red
        labelsize=fs,
    )
    ax.tick_params(
        axis="x",
        which="major",
        direction="out",
        width=lw,
        length=tick_len,
        pad=1.0,
        colors="black",
        labelcolor="black",
        labelsize=fs,
    )

    # ── Y scales (aligned) ────────────────────────────────────────────────────
    l_min, l_max, l_ticks, r_min, r_max, r_ticks = _aligned_scales(
        data.all_left_values, data.all_right_values, 6,
        left_stable=(data.left_mode == "stable"),
        right_stable=(data.right_mode == "stable"),
    )

    ax.set_ylim(l_min, l_max)
    ax.set_yticks(l_ticks)
    ax2.set_ylim(r_min, r_max)
    ax2.set_yticks(r_ticks)

    l_step = l_ticks[1] - l_ticks[0] if len(l_ticks) > 1 else 1.0
    r_step = r_ticks[1] - r_ticks[0] if len(r_ticks) > 1 else 1.0
    ax.yaxis.set_major_formatter(
        _mticker.FormatStrFormatter(f"%.{_decimal_places(l_step)}f")
    )
    ax2.yaxis.set_major_formatter(
        _mticker.FormatStrFormatter(f"%.{_decimal_places(r_step)}f")
    )

    # ── Horizontal gridlines at left tick positions ───────────────────────────
    for y in l_ticks:
        ax.axhline(
            y,
            color=_GRID_COLOR,
            linestyle="--",
            linewidth=_GRID_LW,
            alpha=_GRID_ALPHA,
            zorder=0,
        )

    # ── Axis labels ───────────────────────────────────────────────────────────
    ax.set_ylabel(data.left_label, color=_LEFT_COLOR, fontsize=fs, labelpad=1)
    ax2.set_ylabel(data.right_label, color=_RIGHT_COLOR, fontsize=fs, labelpad=1)

    # ── X-axis ticks and limits ───────────────────────────────────────────────
    ax.set_xticks(x_pos)
    ax.set_xticklabels(data.x_values, fontsize=fs)
    margin = 0.5 if n_x > 1 else 1.0
    ax.set_xlim(-margin, n_x - 1 + margin)

    # ── Plot lines ────────────────────────────────────────────────────────────
    line_lw = 1.0
    ms = 3.0
    n_between = data.interp_pts  # 0 = disabled

    for g_idx, group in enumerate(data.groups):
        ls = _LINE_STYLES[g_idx % len(_LINE_STYLES)]
        ly = data.left_data[group]
        ry = data.right_data[group]

        if n_between > 0:
            seed_l = hash(tuple(round(v, 6) for v in ly)) & 0x7FFFFFFF
            seed_r = hash(tuple(round(v, 6) for v in ry)) & 0x7FFFFFFF
            xl, yl = _interp_jitter(ly, n_between, seed=seed_l + g_idx)
            xr, yr = _interp_jitter(ry, n_between, seed=seed_r + g_idx)
            # Thin wiggly connecting line (no markers on the line itself)
            ax.plot(xl, yl, color=_LEFT_COLOR, linestyle=ls,
                    linewidth=line_lw * 0.5, marker="none", zorder=3, alpha=0.7)
            ax2.plot(xr, yr, color=_RIGHT_COLOR, linestyle=ls,
                     linewidth=line_lw * 0.5, marker="none", zorder=3, alpha=0.7)
            # Hollow square markers only at strictly interpolated positions
            # (skip integer x values which correspond to original data points)
            def _interp_only(xs, ys):
                pairs = [(x, y) for x, y in zip(xs, ys)
                         if abs(x - round(x)) > 1e-9]
                if not pairs:
                    return [], []
                return zip(*pairs)
            xl_i, yl_i = _interp_only(xl, yl)
            xr_i, yr_i = _interp_only(xr, yr)
            sq_ms = ms * 0.65          # square side ≈ circle diameter × 0.65
            ax.plot(list(xl_i), list(yl_i), linestyle="none",
                    marker=_RECT_MARKER, markersize=sq_ms,
                    markerfacecolor="none", markeredgecolor=_LEFT_COLOR,
                    markeredgewidth=0.45, alpha=0.75, zorder=3)
            ax2.plot(list(xr_i), list(yr_i), linestyle="none",
                     marker=_RECT_MARKER, markersize=sq_ms,
                     markerfacecolor="none", markeredgecolor=_RIGHT_COLOR,
                     markeredgewidth=0.45, alpha=0.75, zorder=3)
            # Original data points — filled squares, on top
            ax.plot(x_pos, ly, color=_LEFT_COLOR, linestyle="none",
                    marker=_RECT_MARKER, markersize=ms,
                    markerfacecolor=_LEFT_COLOR, markeredgewidth=0,
                    alpha=1.0, zorder=5)
            ax2.plot(x_pos, ry, color=_RIGHT_COLOR, linestyle="none",
                     marker=_RECT_MARKER, markersize=ms,
                     markerfacecolor=_RIGHT_COLOR, markeredgewidth=0,
                     alpha=1.0, zorder=5)
        else:
            ax.plot(
                x_pos, ly, color=_LEFT_COLOR, linestyle=ls,
                linewidth=line_lw, marker=_RECT_MARKER, markersize=ms,
                markerfacecolor=_LEFT_COLOR, markeredgewidth=0, zorder=3,
            )
            ax2.plot(
                x_pos, ry, color=_RIGHT_COLOR, linestyle=ls,
                linewidth=line_lw, marker=_RECT_MARKER, markersize=ms,
                markerfacecolor=_RIGHT_COLOR, markeredgewidth=0, zorder=3,
            )

    # ── Caption (below x-axis) ────────────────────────────────────────────────
    if data.caption:
        ax.set_xlabel(data.caption, fontsize=fs + 1, labelpad=1, color="black")


# ── Renderer ──────────────────────────────────────────────────────────────────

class SensitivityRenderer(BaseRenderer):
    """Renders a grid of sensitivity-study dual-axis line charts."""

    def _draw(self, fig: Figure, ax: Axes, data: object) -> None:  # pragma: no cover
        raise NotImplementedError(
            "Use render_sensitivity(datasets) instead of render(data)."
        )

    def render_sensitivity(self, datasets: List[SensitivityData]) -> None:
        """Build and save the sensitivity grid figure.

        Parameters
        ----------
        datasets:
            One :class:`SensitivityData` per panel, left-to-right, top-to-bottom.
        """
        cfg = self.config
        self._apply_rcparams()

        n = len(datasets)
        n_cols, n_rows = _determine_grid(n)

        # Each CELL (full subplot area) has aspect ratio φ:1.
        cell_w_pt = cfg.width_pt / n_cols
        cell_h_pt = cell_w_pt / PHI
        fig_w_in  = cfg.width_in
        fig_h_in  = n_rows * cell_h_pt / PT_PER_INCH

        fig = plt.figure(figsize=(fig_w_in, fig_h_in))
        axs = [fig.add_subplot(n_rows, n_cols, i + 1) for i in range(n)]

        for ax, data in zip(axs, datasets):
            self._configure_spines(ax)   # sets linewidth + clip_on baseline
            self._configure_ticks(ax)    # sets tick direction/size baseline
            _draw_panel(fig, ax, data, cfg, n_cols=n_cols)

        # Padding: minimal between panels so twin-axis tick labels don't clash.
        fig.tight_layout(pad=0.2, w_pad=0.2, h_pad=0.4)

        self._save(fig)
        plt.close(fig)
