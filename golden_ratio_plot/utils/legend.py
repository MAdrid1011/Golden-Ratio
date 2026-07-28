"""Shared legend utilities used by all renderer modules.

Functions
---------
greedy_rows          — pack legend entries into as few rows as possible
make_legend_kw       — return the standard legend keyword dict
stack_legend_rows    — draw stacked row legends at y=1.01, return artist list
finalize_legend_rows — reposition rows precisely after canvas.draw()
"""

from __future__ import annotations

from typing import List, Tuple

from matplotlib.axes import Axes

# Char-width factor for legend text.  Smaller than the group-label factor
# because legend entries contain many narrow characters (digits, +, -, parens).
LEGEND_CHAR_WIDTH_FACTOR: float = 0.50


def greedy_rows(
    labels: List[str],
    handles: list,
    available_pt: float,
    font_size: float,
) -> List[Tuple[list, List[str]]]:
    """Greedy left-to-right bin packing of legend entries into rows.

    Parameters
    ----------
    labels, handles:
        Parallel sequences of text labels and matplotlib artist handles.
    available_pt:
        Total horizontal space available for the legend row in points.
        Pass ``cfg.width_pt * AXES_WIDTH_FRACTION`` for axis-aligned legends
        or ``cfg.width_pt`` for full-figure-width legends.
    font_size:
        Font size in points used to estimate item widths.

    Returns
    -------
    List of ``(handles_subset, labels_subset)`` ordered **top-to-bottom**
    (row 0 = topmost row in the figure).
    """
    col_gap = 1.618 * font_size
    item_widths = [
        (0.7 + 0.618) * font_size + len(lbl) * font_size * LEGEND_CHAR_WIDTH_FACTOR
        for lbl in labels
    ]

    rows: List[Tuple[list, List[str]]] = []
    cur_h: list = []
    cur_l: List[str] = []
    cur_w = 0.0

    for h, lbl, w in zip(handles, labels, item_widths):
        if not cur_l:
            cur_h, cur_l, cur_w = [h], [lbl], w
        elif cur_w + col_gap + w <= available_pt:
            cur_h.append(h)
            cur_l.append(lbl)
            cur_w += col_gap + w
        else:
            rows.append((cur_h, cur_l))
            cur_h, cur_l, cur_w = [h], [lbl], w

    if cur_l:
        rows.append((cur_h, cur_l))

    return rows


def make_legend_kw(font_size: float) -> dict:
    """Return the standard ACM legend keyword arguments."""
    return dict(
        frameon=False,
        fontsize=font_size,
        handlelength=1.0,
        handleheight=1.0,
        handletextpad=0.4,
        columnspacing=0.5,
        labelspacing=0.0,
        borderpad=0.0,
        borderaxespad=0.0,
    )


def stack_legend_rows(
    ax: Axes,
    rows: List[Tuple[list, List[str]]],
    font_size: float,
) -> List:
    """Draw legend rows stacked just above the axes.

    Rows are drawn bottom-to-top so that the final ``ax.legend()`` call
    (the topmost row) is the one ``tight_layout`` reserves space for.
    Earlier rows are preserved via ``ax.add_artist()``.

    Parameters
    ----------
    ax:     Target axes.
    rows:   Output of :func:`greedy_rows` — list of (handles, labels) top-to-bottom.
    font_size: Font size in points.

    Returns
    -------
    ``all_legs`` — list of legend artists (bottom row first, top row last).
    Call :func:`finalize_legend_rows` after ``canvas.draw()`` to reposition.
    """
    kw = make_legend_kw(font_size)
    all_legs: list = []
    for row_handles, row_labels in reversed(rows):
        leg = ax.legend(
            row_handles, row_labels,
            loc="lower right",
            bbox_to_anchor=(1.0, 1.002),
            ncol=len(row_labels),
            **kw,
        )
        all_legs.append(leg)
    for leg in all_legs[:-1]:
        ax.add_artist(leg)
    return all_legs


def finalize_legend_rows(
    ax: Axes,
    all_legs: list,
    n_color_rows: int,
    renderer,
) -> None:
    """Measure legend row heights and reposition them precisely.

    Must be called after ``fig.tight_layout()`` and ``fig.canvas.draw()``
    so that pixel extents are available.

    Parameters
    ----------
    ax:            The axes the legends belong to.
    all_legs:      List returned by :func:`stack_legend_rows` (or
                   ``_draw_legend_init`` in ablation), bottom row first.
    n_color_rows:  Number of color/patch rows (vs. the optional mapping row).
    renderer:      ``fig.canvas.get_renderer()`` result.
    """
    if not all_legs:
        return

    ax_height_px  = ax.get_window_extent(renderer).height
    leg_height_px = all_legs[0].get_window_extent(renderer).height
    row_step = leg_height_px / ax_height_px

    for row_idx, leg in enumerate(all_legs[:n_color_rows]):
        y = 1.002 + row_idx * row_step
        leg.set_bbox_to_anchor((1.0, y), transform=ax.transAxes)

    if len(all_legs) > n_color_rows:
        y_map = 1.002 + n_color_rows * row_step
        all_legs[n_color_rows].set_bbox_to_anchor((1.0, y_map), transform=ax.transAxes)
