"""Comparison + decomposition bar chart renderer.

Each group has *n_bars* bars drawn side by side for comparison.  Every bar can
optionally be decomposed into stacked segments.

Color system
------------
One distinct hue is assigned to each comparison bar (harmonious but
contrastive); segments within a bar use a dark-to-light lightness ramp at that
hue (bottom segment darkest, top lightest).

Spacing
-------
  intra-group gap (between bars in same group)  = bar_width / φ  ≈ 0.618
  inter-group gap (between groups)              = bar_width × φ  ≈ 1.618

A thin vertical separator is drawn between groups when *n_bars* > 2.
"""

from __future__ import annotations

from typing import Dict, List, Tuple  # Tuple kept for _segment_colors return type

import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from golden_ratio_plot.config import PHI, PlotConfig
from golden_ratio_plot.reader import DecompData
from golden_ratio_plot.renderer.ablation import _group_labels
from golden_ratio_plot.renderer.base import BaseRenderer
from golden_ratio_plot.utils.colors import ablation_palette
from golden_ratio_plot.utils.labels import AXES_WIDTH_FRACTION as _AXES_WIDTH_FRACTION
from golden_ratio_plot.utils.labels import vcenter_xticklabels as _vcenter_xticklabels
from golden_ratio_plot.utils.legend import (
    finalize_legend_rows as _finalize_legend_rows,
    greedy_rows as _greedy_rows_util,
    make_legend_kw as _make_legend_kw,
    stack_legend_rows as _stack_legend_rows,
)
from golden_ratio_plot.utils.ticks import nice_range

# ── Color constants ────────────────────────────────────────────────────────────

# Hues for up to 6 comparison bars.
#   n=2 : violet-blue (255°) + sky-blue (205°)   — analogous cool pair
#   n=3 : + amber (35°)                           — warm triad accent
#   n=4 : + rose (345°)                           — split-complementary warmth
#   n=5 : + teal (160°)
#   n=6 : + lime (80°)
_BAR_HUES: List[float] = [255.0, 205.0, 35.0, 345.0, 160.0, 80.0]

_SAT: float = 0.62          # saturation shared by all bar/segment colors
_SEG_L_DARK:  float = 0.35  # lightness of the bottom (darkest) segment
_SEG_L_LIGHT: float = 0.72  # lightness of the top (lightest) segment
_BAR_L_SOLID: float = 0.52  # lightness of an unsegmented (solid) bar

_SEP_LW:    float = 0.8
_SEP_COLOR: str   = "black"


def _bar_hues(n_bars: int) -> List[float]:
    """Return *n_bars* hue values, one per comparison bar."""
    if n_bars <= len(_BAR_HUES):
        return _BAR_HUES[:n_bars]
    # For more than 6 bars distribute across 300° of the wheel (avoids the
    # murky yellow-green region between 90° and 160°).
    return [(255.0 + 300.0 * i / n_bars) % 360.0 for i in range(n_bars)]


def _segment_colors(
    bar_idx: int, n_bars: int, n_seg: int
) -> List[Tuple[float, float, float]]:
    """Return *n_seg* RGB colors for bar *bar_idx* (index 0 = bottom = darkest)."""
    hue = _bar_hues(n_bars)[bar_idx]
    if n_seg == 1:
        return ablation_palette(
            1, hue=hue, l_start=_BAR_L_SOLID, l_end=_BAR_L_SOLID,
            saturation=_SAT,
        )
    # Index 0 → darkest (l_start); last → lightest (l_end).
    return ablation_palette(
        n_seg, hue=hue, l_start=_SEG_L_DARK, l_end=_SEG_L_LIGHT,
        saturation=_SAT,
    )




# ── Renderer ──────────────────────────────────────────────────────────────────

class DecompRenderer(BaseRenderer):
    """Grouped stacked bar chart for comparison + decomposition."""

    def _draw(self, fig: Figure, ax: Axes, data: DecompData) -> None:
        cfg = self.config
        fs  = cfg.font_size_pt
        lfs = cfg.label_font_size

        n_groups = len(data.groups)
        n_bars   = len(data.bars)
        if n_groups == 0 or n_bars == 0:
            return

        # ── Resolve x-axis label font size early (needed for y-axis too) ──
        cell_width_pt = cfg.width_pt * _AXES_WIDTH_FRACTION / n_groups
        _, group_display, _, xlbl_fs = _group_labels(
            data.groups, cell_width_pt, lfs
        )

        # ── Layout (golden-ratio spacing) ──────────────────────────────────
        bar_w = 1.0
        intra = bar_w / PHI   # gap between bars in same group ≈ 0.618
        inter = bar_w * PHI   # gap between groups            ≈ 1.618

        centers: Dict[Tuple[str, str], float] = {}
        x = inter / 2.0 + bar_w / 2.0
        for g_idx, g in enumerate(data.groups):
            for b_idx, b in enumerate(data.bars):
                centers[(g, b)] = x
                if b_idx < n_bars - 1:
                    x += bar_w + intra
                elif g_idx < n_groups - 1:
                    x += bar_w + inter
        total_w = x + bar_w / 2.0 + inter / 2.0
        ax.set_xlim(0.0, total_w)

        # ── Draw stacked bars ───────────────────────────────────────────────
        y_max_data = 0.0
        for b_idx, bar in enumerate(data.bars):
            segs   = data.segments.get(bar, [""])
            colors = _segment_colors(b_idx, n_bars, len(segs))
            for g in data.groups:
                cx     = centers[(g, bar)]
                bottom = 0.0
                for s_idx, seg in enumerate(segs):
                    val = data.values.get((g, bar, seg), 0.0)
                    ax.bar(cx, val, width=bar_w, bottom=bottom,
                           color=colors[s_idx], zorder=2,
                           edgecolor="black", linewidth=0.5)
                    bottom += val
                y_max_data = max(y_max_data, bottom)
                if bottom > 0:
                    ax.text(
                        cx, bottom, f"{bottom:.1f}",
                        ha="center", va="bottom",
                        fontsize=fs, color="black", zorder=5,
                    )

        # ── Y-axis ──────────────────────────────────────────────────────────
        y_lo = cfg.y_min if cfg.y_min is not None else 0.0
        y_hi = cfg.y_max if cfg.y_max is not None else y_max_data
        axis_min, axis_max, ticks = nice_range(y_lo, y_hi, n=cfg.y_ticks,
                                               top_padding_intervals=0.15)
        if cfg.y_min is None:
            axis_min = 0.0
            ticks = [t for t in ticks if t >= 0.0]

        # Ensure value labels (drawn at va="bottom" above each bar) are not
        # clipped by the top spine.  Estimate the text height in data units:
        #   clearance ≈ font_size_pt / axes_height_pt × data_range
        # Axes height is roughly 65 % of the figure height in points.
        _axes_h_pt = cfg.height_in * 72.0 * 0.65
        _label_gap = (axis_max - axis_min) * fs * 1.6 / _axes_h_pt
        if y_hi + _label_gap > axis_max:
            axis_max = y_hi + _label_gap

        ax.set_ylim(axis_min, axis_max)
        ax.set_yticks(ticks)

        # ── Horizontal gridlines (same style as ablation) ────────────────────
        ax.set_axisbelow(True)
        ax.yaxis.grid(
            True,
            linestyle="--",
            linewidth=0.5,
            color="#CCCCCC",
            zorder=0,
        )

        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(
                lambda v, _: f"{v:.0f}" if v == int(v) else f"{v:.1f}"
            )
        )
        ax.tick_params(axis="y", which="major", pad=1.5)
        ax.set_ylabel(data.y_label, fontsize=fs, labelpad=2)

        # ── X-axis labels ────────────────────────────────────────────────────
        group_centers = [
            sum(centers[(g, b)] for b in data.bars) / n_bars
            for g in data.groups
        ]
        ax.set_xticks(group_centers)
        ax.set_xticklabels(group_display, fontsize=xlbl_fs)
        for lbl in ax.get_xticklabels():
            lbl.set_multialignment("center")
        ax.tick_params(axis="x", which="both", length=0)

        # Vertically centre short labels within the tallest (multi-line) row.
        _vcenter_xticklabels(ax, xlbl_fs)

        # ── Group separators when n_bars > 2 ────────────────────────────────
        if n_bars > 2:
            for i in range(n_groups - 1):
                cx_last = centers[(data.groups[i],     data.bars[-1])]
                cx_next = centers[(data.groups[i + 1], data.bars[0])]
                sep_x   = (cx_last + bar_w / 2.0 + cx_next - bar_w / 2.0) / 2.0
                ax.axvline(sep_x, color=_SEP_COLOR, linewidth=_SEP_LW, zorder=3)

        # ── Legend (ablation-style: above axes, right-aligned) ─────────────
        handles: List[mpatches.Patch] = []
        labels:  List[str]            = []
        for b_idx, bar in enumerate(data.bars):
            segs   = data.segments.get(bar, [""])
            colors = _segment_colors(b_idx, n_bars, len(segs))
            if len(segs) == 1 and segs[0] == "":
                handles.append(
                    mpatches.Patch(facecolor=colors[0], edgecolor="black", linewidth=0.4)
                )
                labels.append(bar)
            else:
                for s_idx, seg in enumerate(segs):
                    handles.append(
                        mpatches.Patch(facecolor=colors[s_idx], edgecolor="black", linewidth=0.4)
                    )
                    labels.append(seg)

        # Use full figure width for row packing (short labels fit in one row).
        rows = _greedy_rows_util(labels, handles, cfg.width_pt, xlbl_fs)
        all_legs = _stack_legend_rows(ax, rows, xlbl_fs)

        # ── Caption ─────────────────────────────────────────────────────────
        if data.caption:
            ax.set_xlabel(data.caption, fontsize=fs + 1, labelpad=2, color="black")

        # ── Finalise layout and legend row positions ─────────────────────────
        fig.tight_layout(pad=0.3)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        _finalize_legend_rows(ax, all_legs, len(rows), renderer)
