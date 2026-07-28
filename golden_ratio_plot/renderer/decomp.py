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

import colorsys
import math
from typing import Dict, List, Tuple  # Tuple kept for _segment_colors return type

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from golden_ratio_plot.config import PHI, PlotConfig
from golden_ratio_plot.reader import DecompData
from golden_ratio_plot.renderer.ablation import _group_labels
from golden_ratio_plot.renderer.base import BaseRenderer
from golden_ratio_plot.utils.colors import ablation_palette
from golden_ratio_plot.utils.colors import palette_from_config
from golden_ratio_plot.utils.labels import AXES_WIDTH_FRACTION as _AXES_WIDTH_FRACTION
from golden_ratio_plot.utils.labels import vcenter_xticklabels as _vcenter_xticklabels
from golden_ratio_plot.utils.legend import (
    finalize_legend_rows as _finalize_legend_rows,
    greedy_rows as _greedy_rows_util,
    make_legend_kw as _make_legend_kw,
    stack_legend_rows as _stack_legend_rows,
)
from golden_ratio_plot.utils.ticks import nice_range, nice_ticks

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

_SEP_LW:    float = 1.0
_SEP_COLOR: str   = "black"
_PARENT_LABEL_GAP_PT: float = 2.0
_PARENT_BOUNDARY_PAD_PT: float = 1.0


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


def _segment_colors_from_base(
    base_rgb: Tuple[float, float, float],
    n_seg: int,
) -> List[Tuple[float, float, float]]:
    """Return a segment lightness ramp using the hue of a custom base color."""
    hue, _, saturation = colorsys.rgb_to_hls(*base_rgb)
    saturation = max(0.20, saturation)
    if n_seg == 1:
        return [base_rgb]
    if n_seg < 1:
        return []
    return [
        colorsys.hls_to_rgb(
            hue,
            _SEG_L_DARK + i * (_SEG_L_LIGHT - _SEG_L_DARK) / (n_seg - 1),
            saturation,
        )
        for i in range(n_seg)
    ]


def _colors_for_segments(
    bar_idx: int,
    n_bars: int,
    n_seg: int,
    custom_colors: List[Tuple[float, float, float]],
    use_custom_palette: bool,
) -> List[Tuple[float, float, float]]:
    if use_custom_palette and bar_idx < len(custom_colors):
        return _segment_colors_from_base(custom_colors[bar_idx], n_seg)
    return _segment_colors(bar_idx, n_bars, n_seg)


def _decomp_legend_rows(
    data: DecompData,
    custom_colors: List[Tuple[float, float, float]],
    use_custom_palette: bool,
    width_pt: float,
    font_size: float,
    compact: bool = False,
    compact_rows: int = 1,
    bar_legend_title: str = "Path",
    segment_legend_title: str = "Stage",
    legend_note_first: bool = False,
    inline_legend_note: bool = False,
    bar_only: bool = False,
) -> List[Tuple[list, List[str]]]:
    """Build legend rows for decomp charts.

    When every comparison bar is stacked by the same segment list, use one
    legend row per comparison bar.  This makes comparison-decomposition charts
    read as "bar name: segment1 segment2 ..." instead of showing repeated
    segment labels without the bar context.
    """
    if bar_only:
        handles: list = []
        labels: List[str] = []
        for b_idx, bar in enumerate(data.bars):
            segs = data.segments.get(bar, [""])
            colors = _colors_for_segments(
                b_idx, len(data.bars), len(segs),
                custom_colors, use_custom_palette,
            )
            handles.append(
                mpatches.Patch(
                    facecolor=colors[len(colors) // 2],
                    edgecolor="black",
                    linewidth=0.4,
                )
            )
            labels.append(bar)
        return _greedy_rows_util(labels, handles, width_pt, font_size)

    if _has_shared_stacked_segments(data) and compact:
            bar_handles: list = [
                mpatches.Patch(facecolor="none", edgecolor="none", linewidth=0.0)
            ]
            bar_labels: List[str] = [f"{bar_legend_title}:"]
            for b_idx, bar in enumerate(data.bars):
                colors = _colors_for_segments(
                    b_idx, len(data.bars), len(data.segments[bar]),
                    custom_colors, use_custom_palette,
                )
                bar_handles.append(
                    mpatches.Patch(
                        facecolor=colors[len(colors) // 2],
                        edgecolor="black",
                        linewidth=0.4,
                    )
                )
                bar_labels.append(bar)

            segs = data.segments[data.bars[0]]
            segment_handles: list = [
                mpatches.Patch(facecolor="none", edgecolor="none", linewidth=0.0)
            ]
            segment_labels: List[str] = [f"{segment_legend_title}:"]
            for s_idx, seg in enumerate(segs):
                lightness = (
                    _SEG_L_DARK
                    if len(segs) == 1
                    else _SEG_L_DARK
                    + s_idx * (_SEG_L_LIGHT - _SEG_L_DARK) / (len(segs) - 1)
                )
                segment_handles.append(
                    mpatches.Patch(
                        facecolor=colorsys.hls_to_rgb(0.0, lightness, 0.0),
                        edgecolor="black",
                        linewidth=0.4,
                    )
                )
                segment_labels.append(seg)

            rows: List[Tuple[list, List[str]]] = []
            if data.legend_note:
                note_row = (
                    [mpatches.Patch(
                        facecolor="none", edgecolor="none", linewidth=0.0
                    )],
                    [data.legend_note],
                )
                if legend_note_first:
                    rows.append(note_row)
            if compact_rows == 2:
                rows.extend([
                    (bar_handles, bar_labels),
                    (segment_handles, segment_labels),
                ])
            else:
                rows.append((
                    bar_handles + segment_handles,
                    bar_labels + segment_labels,
                ))
            if data.legend_note and not legend_note_first:
                rows.append(note_row)
            return rows

    if _all_bars_stacked(data):
        rows: List[Tuple[list, List[str]]] = []
        for b_idx, bar in enumerate(data.bars):
            segs = data.segments.get(bar, [""])
            colors = _colors_for_segments(
                b_idx, len(data.bars), len(segs), custom_colors,
                use_custom_palette,
            )
            handles: list = [
                mpatches.Patch(
                    facecolor="none", edgecolor="none", linewidth=0.0
                )
            ]
            labels: List[str] = [f"{bar}:"]
            for s_idx, seg in enumerate(segs):
                handles.append(
                    mpatches.Patch(
                        facecolor=colors[s_idx],
                        edgecolor="black",
                        linewidth=0.4,
                    )
                )
                labels.append(seg)
            rows.append((handles, labels))
        if data.legend_note:
            note_row = (
                [mpatches.Patch(facecolor="none", edgecolor="none", linewidth=0.0)],
                [data.legend_note],
            )
            if legend_note_first:
                rows.insert(0, note_row)
            else:
                rows.append(note_row)
        return rows

    handles: List[mpatches.Patch] = []
    labels:  List[str]            = []
    for b_idx, bar in enumerate(data.bars):
        segs   = data.segments.get(bar, [""])
        colors = (
            [custom_colors[b_idx]]
            if len(segs) == 1 and segs[0] == ""
            else _colors_for_segments(
                b_idx, len(data.bars), len(segs), custom_colors,
                use_custom_palette,
            )
        )
        if len(segs) == 1 and segs[0] == "":
            handles.append(
                mpatches.Patch(
                    facecolor=colors[0], edgecolor="black", linewidth=0.4
                )
            )
            labels.append(bar)
        else:
            for s_idx, seg in enumerate(segs):
                handles.append(
                    mpatches.Patch(
                        facecolor=colors[s_idx],
                        edgecolor="black",
                        linewidth=0.4,
                    )
                )
                labels.append(seg)

    if data.legend_note and inline_legend_note and labels:
        labels[-1] = f"{labels[-1]} {data.legend_note}"
        return [(handles, labels)]

    note_row = None
    if data.legend_note and not inline_legend_note:
        note_row = (
            [mpatches.Patch(facecolor="none", edgecolor="none", linewidth=0.0)],
            [data.legend_note],
        )
    if data.legend_note and not legend_note_first and not inline_legend_note:
        handles.append(
            mpatches.Patch(facecolor="none", edgecolor="none", linewidth=0.0)
        )
        labels.append(data.legend_note)
    rows = _greedy_rows_util(labels, handles, width_pt, font_size)
    if note_row is not None and legend_note_first:
        rows.insert(0, note_row)
    return rows


def _has_shared_stacked_segments(data: DecompData) -> bool:
    if len(data.bars) <= 1:
        return False
    first = data.segments.get(data.bars[0], [""])
    if not first or (len(first) == 1 and first[0] == ""):
        return False
    for bar in data.bars[1:]:
        segs = data.segments.get(bar, [""])
        if segs != first:
            return False
    return True


def _all_bars_stacked(data: DecompData) -> bool:
    return all(
        segs and not (len(segs) == 1 and segs[0] == "")
        for segs in (data.segments.get(bar, [""]) for bar in data.bars)
    )




# ── Renderer ──────────────────────────────────────────────────────────────────

class DecompRenderer(BaseRenderer):
    """Grouped stacked bar chart for comparison + decomposition."""

    def render_panels(self, datasets: List[DecompData]) -> None:
        """Render vertically stacked decomp panels."""
        if not datasets:
            return
        cfg = self.config
        self._apply_rcparams()
        n = len(datasets)
        ncols = max(1, min(int(getattr(cfg, "panel_cols", 1)), n))
        nrows = math.ceil(n / ncols)
        if cfg.height_pt is not None:
            total_h_in = cfg.height_in
        elif ncols == 1:
            total_h_in = cfg.height_in * (1.0 + 0.16 * n)
        else:
            total_h_in = cfg.height_in * nrows * 1.18
        fig = plt.figure(figsize=(cfg.width_in, total_h_in))
        axes = [fig.add_subplot(nrows, ncols, i + 1) for i in range(n)]
        for idx, ax in enumerate(axes):
            self._configure_spines(ax)
            self._configure_ticks(ax)
            self._draw(fig, ax, datasets[idx], finalize=False)
        if cfg.shared_panel_legend:
            for ax in axes[1:]:
                for leg in getattr(ax, "_golden_ratio_legend_rows", []):
                    leg.remove()
                setattr(ax, "_golden_ratio_legend_rows", [])
        h_pad = 0.9 if ncols > 1 else 1.0 / cfg.font_size_pt
        fig.tight_layout(h_pad=h_pad, pad=0.3)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for ax in axes:
            legs = getattr(ax, "_golden_ratio_legend_rows", [])
            _finalize_legend_rows(ax, legs, len(legs), renderer)
        self._save(fig)
        plt.close(fig)

    def _draw(self, fig: Figure, ax: Axes, data: DecompData, finalize: bool = True) -> None:
        cfg = self.config
        fs  = cfg.font_size_pt
        lfs = cfg.label_font_size

        n_groups = len(data.groups)
        n_bars   = len(data.bars)
        if n_groups == 0 or n_bars == 0:
            return

        # ── Resolve x-axis label font size early (needed for y-axis too) ──
        panel_cols = max(1, int(getattr(cfg, "panel_cols", 1)))
        cell_width_pt = (
            cfg.width_pt * _AXES_WIDTH_FRACTION / panel_cols / n_groups
        )
        x_groups = data.groups
        if cfg.two_level_xaxis and data.minor_group:
            x_groups = [data.minor_group.get(g, g) for g in data.groups]
        _, group_display, _, xlbl_fs = _group_labels(
            x_groups, cell_width_pt, lfs
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
                    pair_gap = (
                        0.0
                        if cfg.pair_last_bars and b_idx == n_bars - 2
                        else intra
                    )
                    x += bar_w + pair_gap
                elif g_idx < n_groups - 1:
                    x += bar_w + inter
        total_w = x + bar_w / 2.0 + inter / 2.0
        ax.set_xlim(0.0, total_w)
        axes_width_pt = (
            cfg.width_pt * _AXES_WIDTH_FRACTION / panel_cols
        )
        physical_bar_width_pt = axes_width_pt * bar_w / total_w
        requested_delta_fs = (
            cfg.segment_delta_font_size_pt
            if cfg.segment_delta_font_size_pt is not None
            else fs
        )
        delta_font_size = min(
            requested_delta_fs,
            max(6.0, physical_bar_width_pt * 0.72),
        )
        requested_boundary_fs = (
            cfg.cumulative_boundary_font_size_pt
            if cfg.cumulative_boundary_font_size_pt is not None
            else fs
        )
        boundary_font_size = min(
            requested_boundary_fs,
            max(6.0, physical_bar_width_pt * 0.28),
        )

        # ── Draw stacked bars ───────────────────────────────────────────────
        y_max_data = 0.0
        right_bar = cfg.decomp_right_bar
        ax2 = ax.twinx() if right_bar and right_bar in data.bars else None
        right_y_max_data = 0.0
        custom_colors = palette_from_config(n_bars, cfg.custom_palette, cfg.palette_hue)
        use_custom_palette = bool(cfg.custom_palette)
        for b_idx, bar in enumerate(data.bars):
            segs   = data.segments.get(bar, [""])
            colors = (
                [custom_colors[b_idx]]
                if len(segs) == 1 and segs[0] == ""
                else _colors_for_segments(
                    b_idx, n_bars, len(segs), custom_colors, use_custom_palette
                )
            )
            for g in data.groups:
                cx     = centers[(g, bar)]
                bottom = 0.0
                target_ax = ax2 if ax2 is not None and bar == right_bar else ax
                for s_idx, seg in enumerate(segs):
                    val = data.values.get((g, bar, seg), 0.0)
                    target_ax.bar(
                        cx, val, width=bar_w, bottom=bottom,
                        color=colors[s_idx], zorder=2,
                        edgecolor="black", linewidth=0.5,
                    )
                    bottom += val
                if (
                    cfg.show_cumulative_boundaries
                    and len(segs) > 1
                    and bottom > 0
                ):
                    _draw_cumulative_boundaries(
                        target_ax,
                        cx=cx,
                        bar_width=bar_w,
                        segments=segs,
                        values=[
                            data.values.get((g, bar, seg), 0.0)
                            for seg in segs
                        ],
                        colors=colors,
                        fontsize=boundary_font_size,
                        decimals=cfg.cumulative_boundary_decimals,
                    )
                if (
                    target_ax is ax
                    and cfg.show_segment_delta
                    and len(segs) == 2
                    and bottom > 0
                ):
                    lower = data.values.get((g, bar, segs[0]), 0.0)
                    upper = data.values.get((g, bar, segs[1]), 0.0)
                    if upper > 0:
                        _draw_segment_delta(
                            ax,
                            cx=cx,
                            bar_width=bar_w,
                            lower=lower,
                            upper=upper,
                            total=bottom,
                            facecolor=colors[1],
                            fontsize=delta_font_size,
                            mode=cfg.segment_delta_mode,
                            decimals=cfg.segment_delta_decimals,
                        )
                if target_ax is ax:
                    y_max_data = max(y_max_data, bottom)
                else:
                    right_y_max_data = max(right_y_max_data, bottom)
                if cfg.show_values and bottom > 0:
                    target_ax.text(
                        cx, bottom, f"{bottom:.1f}",
                        ha="center", va="bottom",
                        fontsize=fs, color="black", zorder=5,
                    )

        # ── Y-axis ──────────────────────────────────────────────────────────
        y_lo = cfg.y_min if cfg.y_min is not None else 0.0
        y_hi = cfg.y_max if cfg.y_max is not None else y_max_data
        if cfg.y_max is not None:
            axis_min = y_lo
            axis_max = cfg.y_max
            if ax2 is not None:
                tick_count = max(2, cfg.y_ticks)
                tick_step = (axis_max - axis_min) / (tick_count - 1)
                ticks = [
                    axis_min + i * tick_step
                    for i in range(tick_count)
                ]
            else:
                ticks = [
                    t for t in nice_ticks(axis_min, axis_max, n=cfg.y_ticks)
                    if axis_min <= t <= axis_max
                ]
        else:
            axis_min, axis_max, ticks = nice_range(
                y_lo, y_hi, n=cfg.y_ticks, top_padding_intervals=0.15
            )
        if cfg.y_min is None:
            axis_min = 0.0
            ticks = [t for t in ticks if t >= 0.0]

        # Ensure value labels (drawn at va="bottom" above each bar) are not
        # clipped by the top spine.  Estimate the text height in data units:
        #   clearance ≈ font_size_pt / axes_height_pt × data_range
        # Axes height is roughly 65 % of the figure height in points.
        _axes_h_pt = cfg.height_in * 72.0 * 0.65
        _label_gap = (axis_max - axis_min) * fs * 1.6 / _axes_h_pt
        if cfg.y_max is None and y_hi + _label_gap > axis_max:
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
                lambda v, _: (
                    f"{v:.0f}" if v == int(v) else f"{v:.1f}"
                ) + cfg.y_tick_suffix
            )
        )
        ax.tick_params(axis="y", which="major", pad=1.5)
        ax.set_ylabel(data.y_label, fontsize=fs, labelpad=2)

        if ax2 is not None:
            right_min = (
                cfg.right_y_min if cfg.right_y_min is not None else 0.0
            )
            right_max = (
                cfg.right_y_max
                if cfg.right_y_max is not None
                else right_y_max_data
            )
            right_ticks = [
                t for t in nice_ticks(right_min, right_max, n=cfg.y_ticks)
                if right_min <= t <= right_max
            ]
            ax2.set_ylim(right_min, right_max)
            ax2.set_yticks(right_ticks)
            ax2.yaxis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda v, _: (
                        f"{v:.0f}" if v == int(v) else f"{v:.1f}"
                    ) + cfg.right_y_tick_suffix
                )
            )
            ax2.set_ylabel(
                cfg.decomp_right_y_label or right_bar,
                fontsize=fs,
                labelpad=2,
            )
            ax2.tick_params(
                axis="y",
                which="major",
                direction="out",
                width=cfg.spine_linewidth_pt,
                length=3.0,
                pad=1.5,
                right=True,
                left=False,
            )
            ax2.tick_params(axis="y", which="minor", length=0)
            for spine_name in ("top", "bottom", "left"):
                ax2.spines[spine_name].set_visible(False)
            ax2.spines["right"].set_linewidth(cfg.spine_linewidth_pt)
            ax2.spines["right"].set_clip_on(False)

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

        parent_boundary_bottom = None
        if cfg.two_level_xaxis and data.major_group:
            parent_label_y, parent_boundary_bottom = _two_level_xaxis_label_layout(
                fig, ax, xlbl_fs, gap_pt=cfg.parent_label_gap_pt
            )
            _draw_parent_xlabels(
                ax, data.groups, group_centers, data.major_group,
                fontsize=xlbl_fs, y=parent_label_y
            )

        # ── Parent-group separators ─────────────────────────────────────────
        separator_xs: List[float] = []
        for i in range(n_groups - 1):
            cx_last = centers[(data.groups[i],     data.bars[-1])]
            cx_next = centers[(data.groups[i + 1], data.bars[0])]
            sep_x = (cx_last + bar_w / 2.0 + cx_next - bar_w / 2.0) / 2.0
            separator_xs.append(sep_x)

        separator_draw = separator_xs
        if cfg.two_level_xaxis and data.major_group:
            separator_draw = _parent_separator_xs(
                data.groups,
                separator_xs,
                data.major_group,
            )

        for sep_x in separator_draw:
            ax.axvline(sep_x, color=_SEP_COLOR, linewidth=_SEP_LW, zorder=3)

        if cfg.two_level_xaxis and data.major_group:
            _draw_two_level_xaxis_boundaries(
                ax,
                data.groups,
                separator_xs,
                data.major_group,
                x_min=0.0,
                x_max=total_w,
                linewidth=_SEP_LW,
                bottom=parent_boundary_bottom,
            )

        # ── Legend (ablation-style: above axes, right-aligned) ─────────────
        legend_width_pt = cfg.width_pt if panel_cols == 1 else (
            cfg.width_pt * _AXES_WIDTH_FRACTION / panel_cols
        )
        rows = _decomp_legend_rows(
            data, custom_colors, use_custom_palette, legend_width_pt, xlbl_fs,
            compact=cfg.compact_decomp_legend,
            compact_rows=cfg.compact_decomp_legend_rows,
            bar_legend_title=cfg.decomp_bar_legend_title,
            segment_legend_title=cfg.decomp_segment_legend_title,
            legend_note_first=cfg.legend_note_first,
            inline_legend_note=cfg.inline_legend_note,
            bar_only=cfg.decomp_bar_only_legend,
        )
        all_legs = _stack_legend_rows(ax, rows, xlbl_fs)
        setattr(ax, "_golden_ratio_legend_rows", all_legs)

        # ── Caption ─────────────────────────────────────────────────────────
        if data.caption:
            ax.set_xlabel(
                data.caption,
                fontsize=fs + 1,
                labelpad=10 if cfg.two_level_xaxis else 2,
                color="black",
            )
            if cfg.two_level_xaxis and panel_cols > 1:
                ax.xaxis.set_label_coords(0.5, -0.240)

        # ── Finalise layout and legend row positions ─────────────────────────
        if finalize:
            fig.tight_layout(pad=0.3)
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            _finalize_legend_rows(ax, all_legs, len(rows), renderer)


def _draw_segment_delta(
    ax: Axes,
    *,
    cx: float,
    bar_width: float,
    lower: float,
    upper: float,
    total: float,
    facecolor: Tuple[float, float, float],
    fontsize: float,
    mode: str,
    decimals: int,
) -> None:
    """Annotate the upper portion of a two-segment bar inside the bar.

    The double-headed arrow spans the second segment.  ``percent`` reports that
    segment as a share of the full bar, matching rejection- or savings-ratio
    annotations.  ``value`` reports the segment's absolute height.
    """
    if upper <= 0.0 or total <= 0.0:
        return

    endpoint_pad = min(upper * 0.06, total * 0.012)
    y0 = lower + endpoint_pad
    y1 = lower + upper - endpoint_pad
    if y1 <= y0:
        return

    ax.annotate(
        "",
        xy=(cx, y1),
        xytext=(cx, y0),
        arrowprops={
            "arrowstyle": "<->",
            "color": "black",
            "linewidth": 0.5,
            "mutation_scale": 5.0,
            "shrinkA": 0.0,
            "shrinkB": 0.0,
        },
        zorder=5,
    )

    if mode == "value":
        label = f"{upper:.{decimals}f}"
    else:
        label = f"{100.0 * upper / total:.{decimals}f}%"

    ax.text(
        cx,
        lower + upper / 2.0,
        label,
        ha="center",
        va="center",
        rotation=90,
        rotation_mode="anchor",
        fontsize=fontsize,
        color="black",
        zorder=6,
        bbox={
            "boxstyle": "square,pad=0.01",
            "facecolor": facecolor,
            "edgecolor": "none",
            "alpha": 1.0,
        },
    )


def _draw_cumulative_boundaries(
    ax: Axes,
    *,
    cx: float,
    bar_width: float,
    segments: List[str],
    values: List[float],
    colors: List[Tuple[float, float, float]],
    fontsize: float,
    decimals: int,
) -> None:
    """Label cumulative values at every boundary of a stacked bar."""
    cumulative = 0.0
    for idx, (segment, value) in enumerate(zip(segments, values)):
        cumulative += value
        if value <= 0.0:
            continue
        value_text = f"{cumulative:.{decimals}f}"
        if decimals > 0:
            value_text = value_text.rstrip("0").rstrip(".")
        label = f"{segment}:{value_text}" if segment else value_text
        ax.hlines(
            cumulative,
            cx - bar_width * 0.46,
            cx + bar_width * 0.46,
            colors="black",
            linewidth=0.35,
            zorder=5,
        )
        ax.text(
            cx,
            cumulative,
            label,
            ha="center",
            va="top",
            fontsize=fontsize,
            color="black",
            zorder=6,
            bbox={
                "boxstyle": "square,pad=0.01",
                "facecolor": colors[idx],
                "edgecolor": "none",
                "alpha": 1.0,
            },
        )


def _draw_parent_xlabels(
    ax: Axes,
    groups: List[str],
    group_centers: List[float],
    parent_map: Dict[str, str],
    *,
    fontsize: float,
    y: float,
) -> None:
    if not groups:
        return
    start = 0
    current = parent_map.get(groups[0], groups[0])
    trans = ax.get_xaxis_transform()
    for i in range(1, len(groups) + 1):
        parent = parent_map.get(groups[i], groups[i]) if i < len(groups) else None
        if parent != current:
            cx = (group_centers[start] + group_centers[i - 1]) / 2.0
            ax.text(
                cx, y, current,
                transform=trans,
                ha="center",
                va="top",
                fontsize=fontsize,
                fontweight="normal",
                clip_on=False,
            )
            if i < len(groups):
                start = i
                current = parent_map.get(groups[i], groups[i])


def _two_level_xaxis_label_layout(
    fig: Figure,
    ax: Axes,
    fontsize: float,
    *,
    gap_pt: float = _PARENT_LABEL_GAP_PT,
) -> Tuple[float, float]:
    """Return parent-label and boundary positions from rendered tick labels."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer)
    tick_labels = [
        lbl for lbl in ax.get_xticklabels()
        if lbl.get_text().strip()
    ]

    if axes_bbox.height <= 0 or not tick_labels:
        line_h_axes = _points_to_axes_y(fig, ax, fontsize * 1.25)
        gap_axes = _points_to_axes_y(fig, ax, gap_pt)
        parent_y = -line_h_axes - gap_axes
        return parent_y, parent_y - line_h_axes

    child_bottom_px = min(
        lbl.get_window_extent(renderer).y0
        for lbl in tick_labels
    )
    parent_top_px = child_bottom_px - _points_to_pixels(
        fig, gap_pt
    )
    parent_y = ax.transAxes.inverted().transform(
        (axes_bbox.x0, parent_top_px)
    )[1]

    parent_bottom_px = parent_top_px - _points_to_pixels(
        fig, fontsize * 1.15 + _PARENT_BOUNDARY_PAD_PT
    )
    parent_bottom_y = ax.transAxes.inverted().transform(
        (axes_bbox.x0, parent_bottom_px)
    )[1]
    return parent_y, parent_bottom_y


def _points_to_pixels(fig: Figure, points: float) -> float:
    return points * fig.dpi / 72.0


def _points_to_axes_y(fig: Figure, ax: Axes, points: float) -> float:
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer)
    if axes_bbox.height <= 0:
        return 0.0
    return _points_to_pixels(fig, points) / axes_bbox.height


def _parent_separator_xs(
    groups: List[str],
    separator_xs: List[float],
    parent_map: Dict[str, str],
) -> List[float]:
    parent_separators: List[float] = []
    for i, sx in enumerate(separator_xs):
        left_parent = parent_map.get(groups[i], groups[i])
        right_parent = parent_map.get(groups[i + 1], groups[i + 1])
        if left_parent != right_parent:
            parent_separators.append(sx)
    return parent_separators


def _draw_two_level_xaxis_boundaries(
    ax: Axes,
    groups: List[str],
    separator_xs: List[float],
    parent_map: Dict[str, str],
    *,
    x_min: float,
    x_max: float,
    linewidth: float,
    bottom: float | None = None,
) -> None:
    trans = ax.get_xaxis_transform()
    parent_bottom = bottom if bottom is not None else -0.205
    parent_boundaries = [x_min, x_max]
    parent_boundaries.extend(_parent_separator_xs(groups, separator_xs, parent_map))

    for sx in parent_boundaries:
        ax.plot(
            [sx, sx],
            [0.0, parent_bottom],
            transform=trans,
            color=_SEP_COLOR,
            linewidth=linewidth,
            clip_on=False,
            zorder=4,
        )
