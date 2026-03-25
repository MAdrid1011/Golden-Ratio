from __future__ import annotations

from typing import List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.transforms as mtransforms
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

# Fraction of figure width available to the axes after y-axis / margins.
_AXES_WIDTH_FRACTION = 0.82
# Approximate width of one character as a fraction of the font size (pt).
# Times New Roman is a proportional font; 0.55 is a conservative average.
_CHAR_WIDTH_FACTOR = 0.55

# Fixed headroom above the tallest bar (or tallest value label) in pt.
_TOP_PAD_PT = 5.0


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
        # Estimate the pt width available per group after y-axis margins.
        cell_width_pt = cfg.width_pt * _AXES_WIDTH_FRACTION / data.n_groups
        use_circled, group_display = _group_labels(
            data.groups, cell_width_pt, cfg.label_font_size
        )

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

        # ── Y-axis range & ticks (provisional) ───────────────────────────────
        all_values = data.all_values()
        # Bar charts should start at 0 by default so bar heights are truthful.
        # Override with --y_min if a different baseline is needed.
        data_min = cfg.y_min if cfg.y_min is not None else 0.0
        data_max = cfg.y_max if cfg.y_max is not None else max(all_values)

        # Provisional axis_max: generous enough to keep ticks inside the axes.
        # The tight 5-pt top margin is applied in a second pass after layout.
        axis_min, axis_max_prov, ticks = nice_range(
            data_min,
            data_max,
            n=cfg.y_ticks,
            top_padding_intervals=0.618,
        )
        ax.set_ylim(axis_min, axis_max_prov)
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
        ax.set_xticklabels(group_display, fontsize=cfg.label_font_size)
        # Centre multi-line tick label text horizontally within each label box.
        for lbl in ax.get_xticklabels():
            lbl.set_multialignment("center")
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
        # Y-axis label comes directly from the CSV value-column header.
        # X-axis title is omitted; group names on tick labels are self-explanatory.
        ax.set_ylabel(data.value_label, fontsize=cfg.label_font_size)

        # ── Legend (horizontal strip above the top spine) ─────────────────────
        color_labels = list(data.labels)
        mapping_labels: List[str] = []
        if use_circled:
            mapping_labels = [
                f"{_CIRCLED[i]} = {name}"
                for i, name in enumerate(data.groups)
                if i < len(_CIRCLED)
            ]

        # legend calls tight_layout internally — final axes dimensions are now stable
        _draw_legend(fig, ax, colors, color_labels, mapping_labels, cfg)

        # ── Second pass: measure display geometry, then tighten top and centre labels ──
        # tight_layout is already done; axes bbox is now stable.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # ── Re-centre single-line x-axis labels (when mixed with two-line labels) ──
        # Strategy: measure the pixel-space vertical centre of every two-line tick
        # label; hide all tick labels; redraw them all with ax.text() + va='center'
        # anchored at that shared centre so single-line labels appear vertically
        # centred in the same space as two-line labels.
        tick_lbls = ax.get_xticklabels()
        two_line_mask = ["\n" in d for d in group_display]
        if any(two_line_mask) and not all(two_line_mask):
            ax_bb = ax.get_window_extent(renderer)
            # Vertical centre (display pixels) of each two-line tick label
            two_line_cy = [
                (tick_lbls[i].get_window_extent(renderer).y0 +
                 tick_lbls[i].get_window_extent(renderer).y1) / 2.0
                for i, is2 in enumerate(two_line_mask) if is2
            ]
            # Use the lowest centre (two-line labels reach furthest below the axis)
            ref_cy_disp = min(two_line_cy)
            # Convert to axes-fraction y so we can use a blended transform
            ref_cy_ax = (ref_cy_disp - ax_bb.y0) / ax_bb.height

            # Hide original tick labels and replace with custom text artists
            for t in tick_lbls:
                t.set_visible(False)
            blended = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
            for xc, lbl_str in zip(group_centers, group_display):
                ax.text(
                    xc, ref_cy_ax, lbl_str,
                    transform=blended,
                    ha="center", va="center",
                    multialignment="center",
                    fontsize=cfg.label_font_size,
                    clip_on=False,
                )

        # ax_bb already captured above; use it for the tight-margin calculation too.
        if not any(two_line_mask) or all(two_line_mask):
            ax_bb = ax.get_window_extent(renderer)
        ax_height_pt = ax_bb.height / (fig.dpi / 72.0)
        cur_ymin, cur_ymax = ax.get_ylim()
        data_per_pt = (cur_ymax - cur_ymin) / ax_height_pt

        top_pad_pt = _TOP_PAD_PT
        if cfg.show_values:
            # Leave room for the value text: approximate its height as font_size_pt
            top_pad_pt += cfg.font_size_pt

        axis_max_tight = data_max + top_pad_pt * data_per_pt
        # Remove ticks that fall above the new ceiling
        tick_step = ticks[1] - ticks[0] if len(ticks) >= 2 else 1.0
        final_ticks = [t for t in ticks if t <= axis_max_tight + tick_step * 1e-9]
        ax.set_ylim(cur_ymin, axis_max_tight)
        ax.set_yticks(final_ticks)


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

def _best_word_split(words: List[str], max_chars: float) -> Optional[str]:
    """Split *words* into two lines that each fit within *max_chars*.

    Tries every split point and returns the split whose longer line is minimal.
    Returns ``None`` when no valid split exists (e.g. a single word is too long).
    """
    best: Optional[str] = None
    best_max_len: float = float("inf")
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        if len(line1) <= max_chars and len(line2) <= max_chars:
            m = max(len(line1), len(line2))
            if m < best_max_len:
                best_max_len = m
                best = line1 + "\n" + line2
    return best


def _group_labels(
    groups: List[str],
    cell_width_pt: float,
    label_font_size: float,
) -> Tuple[bool, List[str]]:
    """Return ``(use_circled, display_labels)``.

    Strategy (no rotation allowed):
      1. If a label fits on one line → keep it.
      2. If it is too long but contains spaces → wrap at the best word boundary
         so both lines stay within *max_chars*.
      3. If it cannot be wrapped helpfully → fall back to parenthesised numerals.

    Vertical centring of single-line labels relative to two-line labels is handled
    in ``_draw`` after ``fig.canvas.draw()`` using display-coordinate measurements.
    """
    max_chars = cell_width_pt / (label_font_size * _CHAR_WIDTH_FACTOR)

    wrapped: List[str] = []
    any_two_line = False

    for g in groups:
        if len(g) <= max_chars:
            wrapped.append(g)
        else:
            split = _best_word_split(g.split(), max_chars)
            if split is None:
                # Unbreakable — fall back to circled numbers for all groups
                display = [
                    _CIRCLED[i] if i < len(_CIRCLED) else str(i + 1)
                    for i in range(len(groups))
                ]
                return True, display
            wrapped.append(split)
            any_two_line = True

    return False, wrapped


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
