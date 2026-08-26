from __future__ import annotations

import colorsys
import math
import re
from typing import Dict, List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.ticker as _mticker
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.transforms import offset_copy
from golden_ratio_plot.config import PHI, PlotConfig
from golden_ratio_plot.reader import AblationData, read_csv
from golden_ratio_plot.renderer.base import BaseRenderer
from golden_ratio_plot.utils.colors import palette_from_config
from golden_ratio_plot.utils.labels import AXES_WIDTH_FRACTION as _AXES_WIDTH_FRACTION
from golden_ratio_plot.utils.labels import vcenter_xticklabels as _vcenter_xticklabels
from golden_ratio_plot.utils.legend import (
    LEGEND_CHAR_WIDTH_FACTOR as _LEGEND_CHAR_WIDTH_FACTOR,
    finalize_legend_rows as _finalize_legend_rows,
    greedy_rows as _greedy_rows_util,
    make_legend_kw as _make_legend_kw,
)
from golden_ratio_plot.utils.ticks import nice_range

# ── Golden-ratio spacing constants ────────────────────────────────────────────
# Spacing hierarchy:  group_gap : bar_gap : bar_width  =  φ² : φ : 1
_PHI2 = PHI * PHI   # ≈ 2.618
_PHI1 = PHI          # ≈ 1.618
_BAR_UNIT = 1.0      # dimensionless unit width; all other sizes relative to this

# Parenthesised numerals (1)(2)(3)… — pure ASCII, compatible with all fonts.
# Unicode circled numerals (①②③) look nicer but are absent from Times New Roman.
_CIRCLED = [f"({i + 1})" for i in range(20)]

# Approximate width of one character as a fraction of the font size (pt).
# Times New Roman is a proportional font; 0.62 is a conservative estimate used
# for group-label wrapping (group labels use label_font_size = fs+2, and
# overflow must be avoided).
_CHAR_WIDTH_FACTOR = 0.62

# A label whose longest line is within strict_max + _STRICT_TOLERANCE chars is
# accepted even if it marginally overflows the cell (~0.5-char = <2 pt excess
# at 6 pt, barely perceptible).  This lets the algorithm settle at 6 pt rather
# than cascading all the way to 5 pt.
_STRICT_TOLERANCE = 0.5

# Fixed headroom above the tallest bar (or tallest value label) in pt.
_TOP_PAD_PT = 5.0
_PARENT_BOUNDARY_PAD_PT = 1.0


class AblationRenderer(BaseRenderer):
    """Renders an ablation-study bar chart following ACM typographic rules.

    Layout summary
    --------------
    Within each group of ``n_labels`` bars:
      - each bar has width  ``w``
      - gap between adjacent bars = ``w × 0.618``  (φ⁻¹)
    Between consecutive groups:
      - gap = ``w × 1.618``  (φ)
      - a vertical separator line is drawn at the midpoint of the gap
    Y-axis top padding = 0.618 × one tick interval  (golden ratio padding)
    Legend internals:
      - square side = font_size × 1.0
      - square→text gap = font_size × 0.618
      - row height = font_size × 1.618
    """

    # ── Public multi-panel API ────────────────────────────────────────────────

    def render_panels(
        self,
        datasets: List[AblationData],
        line_datasets: Optional[List[Optional[AblationData]]] = None,
    ) -> None:
        """Render multiple datasets as vertically stacked panels in one figure.

        Each panel is a full bar chart drawn with the same style as the single-
        panel :meth:`render` path.  An optional subfigure caption stored in
        ``data.caption`` is rendered below each panel as its x-axis label.

        The layout sequence is:

          1. Phase 1 — draw all panels (bars, axes, legend initial positions).
          2. Single ``fig.tight_layout()`` for the whole figure.
          3. Single ``fig.canvas.draw()`` so all bboxes are accurate.
          4. Phase 2 — finalize each panel (tighten margins, reposition legends,
             sync right axis if present).
        """
        if not datasets:
            return
        cfg = self.config
        n = len(datasets)
        ncols = max(1, min(int(getattr(cfg, "panel_cols", 1)), n))
        nrows = math.ceil(n / ncols)
        self._apply_rcparams()

        if cfg.height_pt is not None:
            total_h_in = cfg.height_in
        elif ncols == 1:
            # Historical vertical-panel behavior.
            total_h_in = cfg.height_in * (1.0 + 0.16 * n)
        else:
            # A multi-column grid needs enough vertical space for each row's
            # two-level x labels and legend rows.
            total_h_in = cfg.height_in * nrows * 1.18

        fig = plt.figure(figsize=(cfg.width_in, total_h_in))
        axes = [fig.add_subplot(nrows, ncols, i + 1) for i in range(n)]
        for ax in axes:
            self._configure_spines(ax)
            self._configure_ticks(ax)

        # Phase 1 ─ draw all panels
        _line_list: List[Optional[AblationData]] = (
            list(line_datasets) if line_datasets else [None] * len(datasets)
        )
        # Pad to match length of datasets.
        while len(_line_list) < len(datasets):
            _line_list.append(None)
        states = [
            self._draw_content(fig, ax, data, line_data_override=ld)
            for ax, data, ld in zip(axes, datasets, _line_list)
        ]

        # Target gap between the bottom of one panel's caption and the top of the
        # next panel's content (legend / bars): 1 pt.  h_pad is in font-size units.
        _h_pad = 1.0 / cfg.font_size_pt

        # First tight_layout: allocates space based on initial legend positions.
        fig.tight_layout(h_pad=_h_pad)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # Phase 2 ─ finalize each panel (tighten margins, reposition legends, …)
        for ax, state in zip(axes, states):
            self._draw_finalize(fig, ax, state, renderer)

        # Second tight_layout: legends have been repositioned; let matplotlib
        # re-measure the full figure extent (including captions below and legend
        # rows above) so inter-panel gaps are correctly sized.
        fig.tight_layout(h_pad=_h_pad)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # Re-finalize legend row positions for the new axes heights.
        for ax, state in zip(axes, states):
            _finalize_legend_rows(ax, state["all_legs"], state["n_color_rows"], renderer)

        self._save(fig)
        plt.close(fig)

    # ── Internal draw phases ──────────────────────────────────────────────────

    def _draw(self, fig: Figure, ax: Axes, data: AblationData) -> None:
        """Single-panel draw (called by :meth:`BaseRenderer.render`)."""
        state = self._draw_content(fig, ax, data)
        if self.config.layout_pad is None:
            fig.tight_layout()
        else:
            fig.tight_layout(pad=max(0.0, self.config.layout_pad))
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        self._draw_finalize(fig, ax, state, renderer)

    def _draw_content(
        self,
        fig: Figure,
        ax: Axes,
        data: AblationData,
        line_data_override: Optional[AblationData] = None,
    ) -> Dict:
        """Phase 1: draw all chart content and create initial legend positions.

        Returns a state dict consumed by :meth:`_draw_finalize`.

        ``line_data_override``, when provided, is used as the line-chart data
        instead of loading ``cfg.input_line`` from disk.  This allows
        :meth:`render_panels` to supply a different line CSV per panel.
        """
        cfg = self.config
        colors = palette_from_config(data.n_labels, cfg.custom_palette, cfg.palette_hue)

        # ── Load optional line-chart data ─────────────────────────────────────
        line_data: Optional[AblationData] = None
        ax2: Optional[Axes] = None
        line_color: Optional[Tuple[float, float, float]] = None
        line_y_label = ""
        line_legend_key = ""
        line_data_max = 0.0

        if line_data_override is not None:
            line_data = line_data_override
        elif cfg.input_line:
            line_data = read_csv(cfg.input_line)

        if line_data is not None:
            line_y_label, line_legend_key = _split_label_key(line_data.value_label)
            line_data_max = max(line_data.all_values())
            # Complementary hue for harmonious contrast: blue (210°) → orange (30°)
            line_hue = (cfg.palette_hue + 180.0) % 360.0
            line_color = colorsys.hls_to_rgb(line_hue / 360.0, 0.50, 0.80)

        # ── Determine group label display mode ────────────────────────────────
        panel_cols = max(1, int(getattr(cfg, "panel_cols", 1)))
        cell_width_pt = (
            cfg.width_pt * _AXES_WIDTH_FRACTION / panel_cols / data.n_groups
        )
        x_groups = data.groups
        if cfg.two_level_xaxis and data.minor_group:
            x_groups = [data.minor_group.get(g, g) for g in data.groups]
        use_circled, group_display, rotation_angle, xlbl_fontsize = _group_labels(
            x_groups, cell_width_pt, cfg.label_font_size
        )

        # ── Compute bar positions ─────────────────────────────────────────────
        positions, group_centers, separator_xs, cell_width = _compute_positions(
            data.n_groups, data.n_labels
        )

        # ── Draw bars ─────────────────────────────────────────────────────────
        bar_width = _BAR_UNIT
        for g, group in enumerate(data.groups):
            for l_idx, label in enumerate(data.labels):
                value = data.data.get((group, label))
                if value is None:
                    continue
                x = positions[g][l_idx]
                ax.bar(
                    x,
                    value,
                    width=bar_width,
                    color=colors[l_idx],
                    edgecolor="black",
                    linewidth=0.5,
                    align="center",
                )
                if cfg.show_values:
                    ax.text(
                        x,
                        value,
                        f"{value:g}",
                        ha="center",
                        va="bottom",
                        fontsize=max(4.0, cfg.font_size_pt - 2),
                        clip_on=False,
                    )

        # ── Y-axis range & ticks (provisional) ───────────────────────────────
        all_values = data.all_values()
        data_min = cfg.y_min if cfg.y_min is not None else 0.0
        data_max = cfg.y_max if cfg.y_max is not None else max(all_values)

        # Horizontal value labels need only a small clearance above the bar.
        _top_pad = 0.3 if cfg.show_values else 0.618
        if cfg.exact_y_ticks and cfg.y_min is not None and cfg.y_max is not None:
            tick_count = max(2, cfg.y_ticks)
            axis_min, axis_max_prov = data_min, data_max
            ticks = [
                data_min + i * (data_max - data_min) / (tick_count - 1)
                for i in range(tick_count)
            ]
        else:
            axis_min, axis_max_prov, ticks = nice_range(
                data_min,
                data_max,
                n=cfg.y_ticks,
                top_padding_intervals=_top_pad,
            )
        ax.set_ylim(axis_min, axis_max_prov)
        ax.set_yticks(ticks)

        # ── Horizontal gridlines ──────────────────────────────────────────────
        ax.set_axisbelow(True)
        ax.yaxis.grid(
            True,
            linestyle="--",
            linewidth=0.5,
            color="#CCCCCC",
            zorder=0,
        )

        # ── Line chart on twin right axis ─────────────────────────────────────
        if line_data is not None and line_color is not None:
            ax2 = ax.twinx()

            if line_data.n_labels == 1:
                line_label = line_data.labels[0]
                ys = [line_data.data.get((group, line_label)) for group in data.groups]
                if all(y is not None for y in ys):
                    ranges = [(0, len(data.groups))]
                    if cfg.two_level_xaxis and data.major_group:
                        ranges = []
                        start = 0
                        current = data.major_group.get(data.groups[0], data.groups[0])
                        for i in range(1, len(data.groups) + 1):
                            parent = (
                                data.major_group.get(data.groups[i], data.groups[i])
                                if i < len(data.groups)
                                else None
                            )
                            if parent != current:
                                ranges.append((start, i))
                                if i < len(data.groups):
                                    start = i
                                    current = parent
                    for start, end in ranges:
                        ax2.plot(
                            group_centers[start:end], ys[start:end],
                            color=line_color,
                            linestyle="--",
                            linewidth=0.8,
                            marker="o",
                            markersize=2.0,
                            markerfacecolor=line_color,
                            markeredgewidth=0,
                            zorder=5,
                        )
            else:
                for g, group in enumerate(data.groups):
                    xs = [positions[g][l_idx] for l_idx in range(data.n_labels)]
                    ys = [line_data.data.get((group, label)) for label in data.labels]
                    if any(y is None for y in ys):
                        continue
                    ax2.plot(
                        xs, ys,
                        color=line_color,
                        linestyle="--",
                        linewidth=0.8,
                        marker="o",
                        markersize=2.0,
                        markerfacecolor=line_color,
                        markeredgewidth=0,
                        zorder=5,
                    )

            if cfg.right_y_min is not None or cfg.right_y_max is not None:
                right_min = cfg.right_y_min if cfg.right_y_min is not None else 0.0
                right_max = cfg.right_y_max if cfg.right_y_max is not None else line_data_max
                n_right_ticks = max(2, len(ticks))
                right_step = (right_max - right_min) / (n_right_ticks - 1)
                right_ticks = [right_min + i * right_step for i in range(n_right_ticks)]
                ax2.set_ylim(right_min, right_max)
                ax2.set_yticks(right_ticks)
            else:
                _, r_max_prov, r_ticks_prov = nice_range(
                    0.0, line_data_max, n=cfg.y_ticks, top_padding_intervals=0.618
                )
                ax2.set_ylim(0.0, r_max_prov)
                ax2.set_yticks(r_ticks_prov)
            ax2.set_ylabel(line_y_label, fontsize=max(xlbl_fontsize, cfg.font_size_pt))
            ax2.tick_params(
                axis="y", which="major",
                direction="out",
                width=cfg.spine_linewidth_pt,
                length=3.0,
            )
            ax2.tick_params(axis="y", which="minor", length=0)
            # Hide duplicate spines; keep only the right spine
            for s in ("top", "bottom", "left"):
                ax2.spines[s].set_visible(False)
            ax2.spines["right"].set_linewidth(cfg.spine_linewidth_pt)
            ax2.spines["right"].set_clip_on(False)

        # ── X-axis ticks & group labels ───────────────────────────────────────
        ax.set_xticks(group_centers)
        ax.set_xticklabels(group_display, fontsize=xlbl_fontsize)
        for lbl in ax.get_xticklabels():
            lbl.set_multialignment("center")
        ax.tick_params(axis="x", which="both", length=0)
        ax.set_xlim(0.0, data.n_groups * cell_width)

        # ── Vertical group separators ─────────────────────────────────────────
        separator_draw = separator_xs
        if cfg.two_level_xaxis and data.major_group:
            separator_draw = _parent_separator_xs(
                data.groups,
                separator_xs,
                data.major_group,
            )
        for sx in separator_draw:
            ax.axvline(
                x=sx,
                color="black",
                linewidth=cfg.spine_linewidth_pt,
                linestyle="-",
                zorder=3,
            )

        if cfg.two_level_xaxis and data.major_group:
            parent_y, parent_boundary_bottom = _two_level_xaxis_label_layout(
                fig,
                ax,
                xlbl_fontsize,
                gap_pt=cfg.parent_label_gap_pt,
            )
            _draw_two_level_xaxis_boundaries(
                ax,
                data.groups,
                separator_xs,
                data.major_group,
                x_min=0.0,
                x_max=data.n_groups * cell_width,
                linewidth=cfg.spine_linewidth_pt,
                bottom=parent_boundary_bottom,
            )
            _draw_parent_xlabels(
                ax, data.groups, group_centers, data.major_group,
                fontsize=xlbl_fontsize, y=parent_y
            )

        # ── Axis labels ───────────────────────────────────────────────────────
        left_y_label, _ = _split_label_key(data.value_label)
        ax.set_ylabel(left_y_label, fontsize=max(xlbl_fontsize, cfg.font_size_pt))

        # ── Subfigure caption (below x-axis tick labels) ──────────────────────
        if data.caption:
            if cfg.two_level_xaxis and data.major_group:
                # Anchor the caption to the parent-label row with a physical
                # point offset.  An x-axis label makes tight_layout exchange
                # label padding for axes height because the parent labels are
                # custom artists, producing an unnecessarily large gap.
                caption_transform = offset_copy(
                    ax.transAxes,
                    fig=fig,
                    x=0.0,
                    y=-(xlbl_fontsize + cfg.panel_caption_pad_pt),
                    units="points",
                )
                ax.text(
                    0.5,
                    parent_y,
                    data.caption,
                    transform=caption_transform,
                    ha="center",
                    va="top",
                    fontsize=xlbl_fontsize + 1,
                    clip_on=False,
                )
            else:
                ax.set_xlabel(
                    data.caption,
                    fontsize=xlbl_fontsize + 1,
                    labelpad=0.5,
                )

        # ── Legend — phase 1: create rows at initial y=1.01 ──────────────────
        color_labels = list(data.labels)
        mapping_labels: List[str] = []
        if use_circled:
            mapping_labels = [
                f"{_CIRCLED[i]} = {name}"
                for i, name in enumerate(data.groups)
                if i < len(_CIRCLED)
            ]
        elif data.legend_note and not cfg.inline_legend_note:
            mapping_labels = [data.legend_note]

        all_legs, n_color_rows = _draw_legend_init(
            fig, ax, colors, color_labels, mapping_labels, cfg,
            font_size=xlbl_fontsize,
            line_color=line_color,
            line_legend_key=line_legend_key,
            legend_note=data.legend_note if cfg.inline_legend_note else "",
        )

        top_pad_pt = _TOP_PAD_PT
        if cfg.show_values:
            top_pad_pt += cfg.font_size_pt

        return {
            "ticks": ticks,
            "data_max": data_max,
            "top_pad_pt": top_pad_pt,
            "ax2": ax2,
            "line_data_max": line_data_max,
            "all_legs": all_legs,
            "n_color_rows": n_color_rows,
            "xlbl_fontsize": xlbl_fontsize,
        }

    def _draw_finalize(
        self,
        fig: Figure,
        ax: Axes,
        state: Dict,
        renderer,
    ) -> None:
        """Phase 2: tighten margins, reposition legends, sync right axis.

        Must be called after ``fig.tight_layout()`` and ``fig.canvas.draw()``
        so that all bounding boxes are accurate.
        """
        cfg           = self.config
        ticks         = state["ticks"]
        data_max      = state["data_max"]
        top_pad_pt    = state["top_pad_pt"]
        ax2           = state["ax2"]
        line_data_max = state["line_data_max"]
        all_legs      = state["all_legs"]
        n_color_rows  = state["n_color_rows"]

        # Labels are pre-padded to uniform line count in _group_labels, so
        # tight_layout already has accurate heights — no manual re-centring needed.
        ax_bb = ax.get_window_extent(renderer)
        ax_height_pt = ax_bb.height / (fig.dpi / 72.0)
        cur_ymin, cur_ymax = ax.get_ylim()
        data_per_pt = (cur_ymax - cur_ymin) / ax_height_pt

        # ── Tighten top margin ─────────────────────────────────────────────────
        axis_max_tight = data_max if cfg.y_max is not None else data_max + top_pad_pt * data_per_pt
        tick_step = ticks[1] - ticks[0] if len(ticks) >= 2 else 1.0
        final_ticks = [t for t in ticks if t <= axis_max_tight + tick_step * 1e-9]
        ax.set_ylim(cur_ymin, axis_max_tight)
        ax.set_yticks(final_ticks)

        # ── Reposition legend rows (measure real pixel heights first) ──────────
        _finalize_legend_rows(ax, all_legs, n_color_rows, renderer)

        # ── Sync right axis — physical alignment + clean tick labels ──────────
        if ax2 is not None:
            if cfg.right_y_min is not None or cfg.right_y_max is not None:
                right_ymin = cfg.right_y_min if cfg.right_y_min is not None else 0.0
                right_ymax = cfg.right_y_max if cfg.right_y_max is not None else line_data_max
                n_right_ticks = max(2, len(final_ticks))
                right_step = (right_ymax - right_ymin) / (n_right_ticks - 1)
                right_ticks = [right_ymin + i * right_step for i in range(n_right_ticks)]
                ax2.set_ylim(right_ymin, right_ymax)
                ax2.set_yticks(right_ticks)
                dp = _decimal_places(right_step)
            else:
                left_step = (
                    (final_ticks[1] - final_ticks[0]) if len(final_ticks) >= 2 else 1.0
                )
                scale_min = line_data_max / axis_max_tight if axis_max_tight > 0 else 1.0
                right_step_min = left_step * scale_min
                nice_right_step = _nice_ceil(right_step_min)
                nice_scale = nice_right_step / left_step if left_step > 0 else 1.0

                right_ymax = axis_max_tight * nice_scale
                right_ticks = [i * nice_right_step for i in range(len(final_ticks))]
                ax2.set_ylim(0.0, right_ymax)
                ax2.set_yticks(right_ticks)
                dp = _decimal_places(nice_right_step)
            ax2.yaxis.set_major_formatter(_mticker.FormatStrFormatter(f"%.{dp}f"))

        # ── Vertically centre short x-tick labels within the tallest label's space ─
        xlbl_fs = state.get("xlbl_fontsize", cfg.font_size_pt)
        _vcenter_xticklabels(ax, xlbl_fs)


# ── Position computation ──────────────────────────────────────────────────────

def _compute_positions(
    n_groups: int,
    n_labels: int,
) -> Tuple[List[List[float]], List[float], List[float], float]:
    """Compute x-positions for all bars, group centers, separator x-values, and cell width.

    Spacing hierarchy (all distances expressed as multiples of bar width w):

        inner_gap (between adjacent bars, same group)  = w / φ  ≈ 0.618 w
        margin    (bar edge ↔ separator or spine)       = φ / 2  ≈ 0.809 w
        outer_gap (total edge-to-edge between groups)  = φ      ≈ 1.618 w

    Each group occupies one "cell" of width:
        cell = margin + bar_span + margin
             = 2 × margin + n×w + (n−1)×inner_gap

    The separator is placed at the exact cell boundary, giving equal margin
    (0.809 w) on BOTH sides of every separator line and both spines.

        [spine]─margin─[bar ··· bar]─margin─[sep]─margin─[bar ··· bar]─margin─[spine]
    """
    w = _BAR_UNIT                    # bar width = 1.0
    inner_gap = w / PHI              # ≈ 0.618 — between adjacent bars in same group
    bar_span = n_labels * w + (n_labels - 1) * inner_gap   # left-edge to right-edge
    outer_gap = w * PHI              # ≈ 1.618 — total edge-to-edge gap between groups
    margin = outer_gap / 2           # ≈ 0.809 — each side of every boundary

    cell = 2 * margin + bar_span     # total width of one group's territory

    all_positions: List[List[float]] = []
    group_centers: List[float] = []
    separator_xs: List[float] = []

    for g in range(n_groups):
        cell_start = g * cell
        # Center of first bar: cell_start + margin + w/2
        first_bar_center = cell_start + margin + w / 2
        bar_xs = [first_bar_center + l_idx * (w + inner_gap) for l_idx in range(n_labels)]
        all_positions.append(bar_xs)
        group_centers.append(cell_start + cell / 2)

        if g < n_groups - 1:
            # Separator sits exactly at the cell boundary
            separator_xs.append(cell_start + cell)

    return all_positions, group_centers, separator_xs, cell


def _draw_parent_xlabels(
    ax: Axes,
    groups: List[str],
    group_centers: List[float],
    parent_map: Dict[str, str],
    *,
    fontsize: float,
    y: float,
) -> None:
    """Draw parent labels centered under consecutive child groups."""
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
    gap_pt: float = 2.0,
) -> Tuple[float, float]:
    """Place the parent-label row at a fixed physical gap below child labels."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer)
    tick_labels = [
        label for label in ax.get_xticklabels()
        if label.get_text().strip()
    ]
    if axes_bbox.height <= 0 or not tick_labels:
        line_h_axes = _points_to_axes_y(fig, ax, fontsize * 1.25)
        gap_axes = _points_to_axes_y(fig, ax, gap_pt)
        parent_y = -line_h_axes - gap_axes
        return parent_y, parent_y - line_h_axes

    child_bottom_px = min(
        label.get_window_extent(renderer).y0
        for label in tick_labels
    )
    parent_top_px = child_bottom_px - _points_to_pixels(fig, gap_pt)
    parent_y = ax.transAxes.inverted().transform(
        (axes_bbox.x0, parent_top_px)
    )[1]
    parent_bottom_px = parent_top_px - _points_to_pixels(
        fig,
        fontsize * 1.15 + _PARENT_BOUNDARY_PAD_PT,
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
    """Return separators only where adjacent child groups change parent."""
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
    bottom: float = -0.205,
) -> None:
    """Extend separators into the two-level x-axis label area."""
    trans = ax.get_xaxis_transform()
    parent_boundaries = [x_min, x_max]
    for i, sx in enumerate(separator_xs):
        left_parent = parent_map.get(groups[i], groups[i])
        right_parent = parent_map.get(groups[i + 1], groups[i + 1])
        if left_parent != right_parent:
            parent_boundaries.append(sx)

    for sx in parent_boundaries:
        ax.plot(
            [sx, sx],
            [0.0, bottom],
            transform=trans,
            color="black",
            linewidth=linewidth,
            clip_on=False,
            zorder=4,
        )


# ── Group label helpers ───────────────────────────────────────────────────────

def _best_nline_split(
    words: List[str],
    max_chars: float,
    n: int,
) -> Optional[str]:
    """Split *words* into at most *n* lines each ≤ *max_chars* characters.

    Returns the split with the shortest maximum line length, or ``None`` when
    impossible.  For ``n == 2`` delegates to :func:`_best_word_split` which
    includes mid-word hyphenation.  Higher ``n`` values use plain word
    boundaries only (sufficient for the 3-line case in practice).
    """
    text = " ".join(words)
    if len(text) <= max_chars:
        return text  # already fits in one line; no split needed
    if n <= 1:
        return None
    if n == 2:
        return _best_word_split(words, max_chars)

    best: Optional[str] = None
    best_max: float = float("inf")

    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        if len(line1) > max_chars:
            continue
        rest = _best_nline_split(words[i:], max_chars, n - 1)
        if rest is None:
            continue
        cand = line1 + "\n" + rest
        m = max(len(ln) for ln in cand.split("\n"))
        if m < best_max:
            best_max, best = m, cand

    return best


def _best_word_split(words: List[str], max_chars: float) -> Optional[str]:
    """Split *words* into two lines that each fit within *max_chars*.

    Scoring: primary = minimise max(len(line1), len(line2)); secondary =
    minimise |len(line1) - len(line2)| so balanced splits (e.g. "Roast-\\n
    ed Beef", diff=1) are preferred over unbalanced ones ("Roasted\\nBeef",
    diff=3) when their max-length is equal.  Mid-word hyphenation is always
    considered so it can compete with plain word-boundary splits.
    Returns ``None`` when no valid split exists.
    """
    best: Optional[str] = None
    best_max_len: float = float("inf")
    best_diff: float = float("inf")

    # Minimum chars before (prefix) and after (suffix) a hyphen break.
    # Prevents ugly splits like "S-pinach" or "Beef" → "Bee-f".
    _MIN_PRE, _MIN_SUF = 3, 2

    def _try(h1: str, h2: str, is_hyphen: bool = False) -> None:
        """Record h1/h2 if they improve the current best.

        Primary criterion  : minimise max line length.
        Secondary criterion: prefer clean word-boundary splits over hyphenated
                             ones (avoid "Cook S-pinach" when "Cook Spinach" fits).
        Tertiary criterion : minimise |len(h1) − len(h2)| so balanced
                             hyphenated splits (e.g. "Roast-\\ned Beef", diff=1)
                             are preferred over unbalanced clean splits
                             ("Roasted\\nBeef", diff=3) when both fit.
        """
        nonlocal best, best_max_len, best_diff, best_is_hyphen
        if len(h1) > max_chars or len(h2) > max_chars:
            return
        m = max(len(h1), len(h2))
        d = abs(len(h1) - len(h2))
        better = (
            m < best_max_len
            or (m == best_max_len and (not is_hyphen) and best_is_hyphen)
            or (m == best_max_len and is_hyphen == best_is_hyphen and d < best_diff)
        )
        if better:
            best_max_len, best_diff, best_is_hyphen = m, d, is_hyphen
            best = h1 + "\n" + h2

    best_is_hyphen: bool = True  # will be overwritten on first hit

    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])

        # ── Plain word-boundary split ──────────────────────────────────────
        _try(line1, line2, is_hyphen=False)

        # ── Hyphenate the last word of line1 ──────────────────────────────
        head = words[: i - 1]
        w1 = words[i - 1]
        pre = (" ".join(head) + " ") if head else ""
        for j in range(_MIN_PRE, len(w1) - _MIN_SUF + 1):
            _try(pre + w1[:j] + "-", w1[j:] + (" " + line2 if line2 else ""), True)

        # ── Hyphenate the first word of line2 ─────────────────────────────
        w2 = words[i]
        tail = words[i + 1 :]
        suf = " ".join(tail)
        for j in range(_MIN_PRE, len(w2) - _MIN_SUF + 1):
            _try(
                (line1 + " " if line1 else "") + w2[:j] + "-",
                w2[j:] + (" " + suf if suf else ""),
                True,
            )

    return best


def _try_wrap_all(
    groups: List[str],
    max_chars: float,
    max_lines: int,
) -> Optional[List[str]]:
    """Attempt to wrap every group label to *max_lines* lines of ≤ *max_chars*.

    Returns the list of wrapped strings, or ``None`` if any label cannot fit.
    """
    result: List[str] = []
    for g in groups:
        if len(g) <= max_chars:
            result.append(g)
        else:
            split = _best_nline_split(g.split(), max_chars, max_lines)
            if split is None:
                return None
            result.append(split)
    return result


def _group_labels(
    groups: List[str],
    cell_width_pt: float,
    label_font_size: float,
) -> Tuple[bool, List[str], int, float]:
    """Return ``(use_circled, display_labels, rotation_angle, effective_font_size)``.

    Rotation is **never** used.  Priority order (stops at first success):

    For each font size *f* in ``[label_font_size … 5]``:

      1. **2-line strict** — every line ≤ cell width / (f × char_factor).
      2. **3-line strict** — same limit, up to 3 lines.

    Only solutions where *every* line fits within the cell are accepted, which
    prevents adjacent labels from overlapping.  If no font size down to 5 pt
    produces a valid wrapping, fall back to parenthesised circled numerals.
    """
    _XLBL_MIN_PT = 5.0

    if groups and all(re.fullmatch(r"\(\d+\)", g) for g in groups):
        return False, groups, 0, min(label_font_size, 7.0)

    for f in range(int(label_font_size), max(int(_XLBL_MIN_PT) - 1, int(label_font_size) - 5), -1):
        fs = float(f)
        if fs < _XLBL_MIN_PT:
            break
        strict_max = cell_width_pt / (fs * _CHAR_WIDTH_FACTOR) + _STRICT_TOLERANCE

        # Pass 1: 2-line, strict (no overflow)
        wrapped = _try_wrap_all(groups, strict_max, max_lines=2)
        if wrapped is not None:
            return False, _pad_to_uniform_lines(wrapped), 0, fs

        # Pass 2: 2-line, generous (1.4× threshold — allows slight overflow for
        # labels like "Cut Roa-\nsted Beef" that cannot be split cleanly in 2 lines)
        wrapped = _try_wrap_all(groups, strict_max * 1.4, max_lines=2)
        if wrapped is not None:
            return False, _pad_to_uniform_lines(wrapped), 0, fs

        # Pass 3: 3-line, strict
        wrapped = _try_wrap_all(groups, strict_max, max_lines=3)
        if wrapped is not None:
            return False, _pad_to_uniform_lines(wrapped), 0, fs

    # ── Circled numerals (absolute last resort, no rotation ever) ─────────────
    display = [
        _CIRCLED[i] if i < len(_CIRCLED) else str(i + 1)
        for i in range(len(groups))
    ]
    return True, display, 0, label_font_size


def _pad_to_uniform_lines(labels: List[str]) -> List[str]:
    """Return labels unchanged.

    ``tight_layout`` allocates space based on the tallest label (most newlines)
    naturally, so shorter labels need no trailing-newline padding.  Padding was
    removed because a trailing '\\n' on a short label (e.g. "Dance3\\n") creates
    an invisible empty line that extends below the 2-line labels after
    ``set_pad()`` centering, which ``bbox_inches='tight'`` picks up as
    whitespace at the bottom of the saved figure.
    """
    return list(labels)


# ── Axis-scale helpers ────────────────────────────────────────────────────────

def _nice_ceil(x: float) -> float:
    """Return the smallest value of the form {1, 2, 2.5, 5} × 10^n that is ≥ x."""
    if x <= 0:
        return 1.0
    exp = math.floor(math.log10(x))
    base = 10.0 ** exp
    for k in (1.0, 2.0, 2.5, 5.0, 10.0):
        candidate = k * base
        if candidate >= x - abs(x) * 1e-9:
            return candidate
    return 10.0 * base


def _decimal_places(step: float) -> int:
    """Number of decimal places required to represent *step* without rounding."""
    for d in range(6):
        if abs(round(step * 10 ** d) - step * 10 ** d) < 1e-9:
            return d
    return 2


# ── Label / key helpers ───────────────────────────────────────────────────────

def _split_label_key(text: str) -> Tuple[str, str]:
    """Split ``'Label (Key)'`` into ``('Label', 'Key')``.

    Returns ``(text, '')`` when the string contains no parenthetical suffix.
    Used to separate the y-axis title from the short legend key stored in the
    CSV value-column header, e.g. ``'Average Load Time (Load)'``.
    """
    stripped = text.strip()
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", stripped)
    if not m:
        return stripped, ""
    suffix = m.group(2).strip()
    if suffix in {"%", "ms", "s", "J", "W", "FPS"}:
        return stripped, ""
    return m.group(1).strip(), suffix


# ── Legend drawing ────────────────────────────────────────────────────────────

def _greedy_rows(
    labels: List[str],
    handles: list,
    cfg: "PlotConfig",
    font_size: Optional[float] = None,
) -> List[Tuple[list, List[str]]]:
    """Delegate to :func:`utils.legend.greedy_rows` using the axes-width budget."""
    fs = font_size if font_size is not None else cfg.font_size_pt
    panel_cols = max(1, int(getattr(cfg, "panel_cols", 1)))
    width_pt = cfg.width_pt * _AXES_WIDTH_FRACTION / panel_cols
    return _greedy_rows_util(labels, handles, width_pt, fs)


def _draw_legend_init(
    fig: Figure,
    ax: Axes,
    colors: List[Tuple[float, float, float]],
    color_labels: List[str],
    mapping_labels: List[str],
    cfg: PlotConfig,
    *,
    font_size: Optional[float] = None,
    line_color: Optional[Tuple[float, float, float]] = None,
    line_legend_key: str = "",
    legend_note: str = "",
) -> Tuple[List, int]:
    """Phase 1 of legend drawing: create all legend artists at y=1.01.

    Returns ``(all_legs, n_color_rows)`` where *all_legs* lists every legend
    artist (color rows first, optional mapping row last) and *n_color_rows*
    is the count of color-bar rows.

    Actual pixel measurement and final repositioning happen in
    :func:`_finalize_legend_rows`, which must be called after
    ``fig.tight_layout()`` and ``fig.canvas.draw()``.
    """
    fs = font_size if font_size is not None else cfg.font_size_pt

    # ── Build handles and labels ──────────────────────────────────────────────
    handles = [
        mpatches.Patch(facecolor=c, edgecolor="black", linewidth=0.4)
        for c in colors
    ]
    labels = list(color_labels)

    if line_color is not None and line_legend_key:
        dot_handle = Line2D(
            [0], [0],
            marker="o",
            color="none",
            markerfacecolor=line_color,
            markeredgewidth=0,
            markersize=fs * 0.55,
            linestyle="none",
        )
        handles.append(dot_handle)
        labels.append(line_legend_key)

    if legend_note and labels:
        labels[-1] = f"{labels[-1]} {legend_note}"
        rows = [(handles, labels)]
    else:
        # Greedy bin-packing: rows ordered top-to-bottom.
        rows = _greedy_rows(labels, handles, cfg, font_size=fs)
    n_color_rows = len(rows)

    legend_kw = _make_legend_kw(fs)

    # Stack all rows at y=1.01 (placeholder).  Draw bottom-to-top so the last
    # ax.legend() call (topmost row) is what tight_layout budgets space for.
    all_legs: List = []
    for row_handles, row_labels in reversed(rows):
        leg = ax.legend(
            row_handles, row_labels,
            loc="lower right",
            bbox_to_anchor=(1.0, 1.01),
            ncol=len(row_labels),
            **legend_kw,
        )
        all_legs.append(leg)
    for leg in all_legs[:-1]:
        ax.add_artist(leg)

    # ── Optional mapping row (circled-number → group name) ────────────────────
    if mapping_labels:
        blank = [Line2D([], [], linestyle="none", color="none") for _ in mapping_labels]
        # Provisional position; will be corrected in _finalize_legend_rows.
        leg_map = ax.legend(
            blank,
            mapping_labels,
            loc="lower right",
            bbox_to_anchor=(1.0, 1.01 + n_color_rows),
            ncol=len(mapping_labels),
            frameon=False,
            fontsize=fs,
            handlelength=0.0,
            handleheight=0.0,
            handletextpad=0.0,
            columnspacing=0.5,
            labelspacing=0.0,
            borderpad=0.0,
            borderaxespad=0.0,
        )
        # Preserve topmost color row as an artist so it isn't dropped.
        ax.add_artist(all_legs[-1])
        all_legs.append(leg_map)

    return all_legs, n_color_rows


# _finalize_legend_rows is imported from utils.legend and re-exported here
# for backward compatibility with any external callers.
# (The name is already imported at the top of this module.)
