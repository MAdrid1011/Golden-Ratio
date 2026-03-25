from __future__ import annotations

from typing import List, Optional, Tuple

import matplotlib.patches as mpatches
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from golden_ratio_plot.config import PHI, PlotConfig
from golden_ratio_plot.reader import AblationData
from golden_ratio_plot.renderer.base import BaseRenderer
from golden_ratio_plot.utils.colors import palette_from_config
from golden_ratio_plot.utils.ticks import nice_range

# ── Golden-ratio spacing constants ────────────────────────────────────────────
# Spacing hierarchy:  group_gap : bar_gap : bar_width  =  φ² : φ : 1
_PHI2 = PHI * PHI   # ≈ 2.618
_PHI1 = PHI          # ≈ 1.618
_BAR_UNIT = 1.0      # dimensionless unit width; all other sizes relative to this

# Parenthesised numerals (1)(2)(3)… — pure ASCII, compatible with all fonts.
# Unicode circled numerals (①②③) look nicer but are absent from Times New Roman.
_CIRCLED = [f"({i + 1})" for i in range(20)]

# Maximum characters for a group label before switching to circled numbers
_MAX_GROUP_LABEL_LEN = 12


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

    def _draw(self, fig: Figure, ax: Axes, data: AblationData) -> None:
        cfg = self.config
        colors = palette_from_config(data.n_labels, cfg.custom_palette, cfg.palette_hue)

        # ── Determine group label display mode ────────────────────────────────
        use_circled, group_display = _group_labels(data.groups)

        # ── Compute bar positions ─────────────────────────────────────────────
        positions, group_centers, separator_xs, cell_width = _compute_positions(
            data.n_groups, data.n_labels
        )
        # positions[g][l] → x coordinate of bar (g, l)

        # ── Draw bars ─────────────────────────────────────────────────────────
        bar_width = _BAR_UNIT  # data-space width; matplotlib uses this directly
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
                        fontsize=cfg.font_size_pt,
                        clip_on=False,
                    )

        # ── Y-axis range & ticks ──────────────────────────────────────────────
        all_values = data.all_values()
        data_min = cfg.y_min if cfg.y_min is not None else min(all_values)
        data_max = cfg.y_max if cfg.y_max is not None else max(all_values)

        # Extra padding when values are shown (need room above bar for the text)
        extra_padding = 1.618 if cfg.show_values else 1.0
        axis_min, axis_max, ticks = nice_range(
            data_min,
            data_max,
            n=cfg.y_ticks,
            top_padding_intervals=0.618 * extra_padding,
        )
        ax.set_ylim(axis_min, axis_max)
        ax.set_yticks(ticks)

        # ── Horizontal gridlines ──────────────────────────────────────────────
        # Light-gray dashed lines at every y-tick, drawn below all other artists.
        ax.set_axisbelow(True)
        ax.yaxis.grid(
            True,
            linestyle="--",
            linewidth=0.5,
            color="#CCCCCC",
            zorder=0,
        )

        # ── X-axis ticks & group labels ───────────────────────────────────────
        ax.set_xticks(group_centers)
        ax.set_xticklabels(group_display, fontsize=cfg.font_size_pt)
        # Remove x-axis tick marks (groups are not numeric positions)
        ax.tick_params(axis="x", which="both", length=0)

        # X limits: spine-to-outer-bar-edge = margin = φ/2 on both sides
        ax.set_xlim(0.0, data.n_groups * cell_width)

        # ── Vertical group separators ─────────────────────────────────────────
        for sx in separator_xs:
            ax.axvline(
                x=sx,
                color="black",
                linewidth=cfg.spine_linewidth_pt,
                linestyle="-",
                zorder=3,
            )

        # ── Axis labels ───────────────────────────────────────────────────────
        # X-axis: group names on the tick labels are self-explanatory;
        # the axis title is intentionally omitted for ablation charts.
        ax.set_ylabel(cfg.y_axis_label, fontsize=cfg.font_size_pt)

        # ── Legend (horizontal strip above the top spine) ─────────────────────
        color_labels = list(data.labels)
        mapping_labels: List[str] = []
        if use_circled:
            mapping_labels = [
                f"{_CIRCLED[i]} = {name}"
                for i, name in enumerate(data.groups)
                if i < len(_CIRCLED)
            ]

        _draw_legend(fig, ax, colors, color_labels, mapping_labels, cfg)


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


# ── Group label helpers ───────────────────────────────────────────────────────

def _group_labels(groups: List[str]) -> Tuple[bool, List[str]]:
    """Return ``(use_circled, display_labels)``.

    If any group name is longer than ``_MAX_GROUP_LABEL_LEN`` characters the
    function switches all labels to circled numerals so the x-axis stays clean.
    """
    if any(len(g) > _MAX_GROUP_LABEL_LEN for g in groups):
        display = [_CIRCLED[i] if i < len(_CIRCLED) else str(i + 1) for i in range(len(groups))]
        return True, display
    return False, list(groups)


# ── Legend drawing ────────────────────────────────────────────────────────────

def _draw_legend(
    fig: Figure,
    ax: Axes,
    colors: List[Tuple[float, float, float]],
    color_labels: List[str],
    mapping_labels: List[str],
    cfg: PlotConfig,
) -> None:
    """Draw the legend as a horizontal strip just above the top spine.

    Layout (golden-ratio proportions, font size = ``fs``):
      - Swatch side   = fs × 1.0  (square)
      - Swatch→text   = fs × 0.618
      - Item spacing  = fs × 1.618  (column gap)
      - The strip sits just outside the top axes spine, inside the figure.

    All color items go on the first row. If long-group-name mapping entries
    exist they wrap onto a second row.
    """
    fs = cfg.font_size_pt

    # ── Build handles and labels ──────────────────────────────────────────────
    handles = [
        mpatches.Patch(facecolor=c, edgecolor="black", linewidth=0.4)
        for c in colors
    ]
    labels = list(color_labels)

    # Main legend: one horizontal row, anchored just above the top spine.
    # bbox_to_anchor=(0, 1.0) in axes coords = top-left corner of the axes.
    # loc='lower left' means the bottom-left of the legend box lands there.
    # A small vertical offset (0.02) gives a 1-line gap between spine and legend.
    leg = ax.legend(
        handles,
        labels,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.01),
        ncol=len(labels),
        frameon=False,
        fontsize=fs,
        # Square swatch: handlelength ≈ handleheight in "em" units (1 em = fs pt).
        # 0.7 em at 7 pt ≈ 4.9 pt ≈ a small but legible square.
        handlelength=0.7,
        handleheight=0.7,
        handletextpad=0.618,          # gap square→text  = φ⁻¹ × 1 em
        columnspacing=1.618,          # gap item→item    = φ  × 1 em
        borderpad=0.0,
        borderaxespad=0.0,
    )

    # ── Optional second row: group-number mapping ─────────────────────────────
    if mapping_labels:
        from matplotlib.lines import Line2D
        blank = [Line2D([], [], linestyle="none", color="none") for _ in mapping_labels]
        leg2 = ax.legend(
            blank,
            mapping_labels,
            loc="lower right",
            # Shift up one row above leg; approximation: one line ≈ fs × 1.618 pt
            bbox_to_anchor=(1.0, 1.01 + (fs * 1.618) / (cfg.height_in * 72.0)),
            ncol=len(mapping_labels),
            frameon=False,
            fontsize=fs,
            handlelength=0.0,
            handleheight=0.0,
            handletextpad=0.0,
            columnspacing=1.618,
            borderpad=0.0,
            borderaxespad=0.0,
        )
        ax.add_artist(leg)   # restore first legend (add_artist keeps both)

    # Let tight_layout adjust the axes downward to make room for the strip.
    fig.tight_layout()
