from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

PHI = 1.6180339887  # golden ratio
PT_PER_INCH = 72.0

# Default figure heights for ablation and decomp charts.
_DEFAULT_HEIGHT_SINGLE_PT = 120.0          # single-column (≤ 240 pt wide)
_DEFAULT_HEIGHT_WIDE_PT   = 240.0 / PHI   # double-column (> 240 pt wide) ≈ 148 pt


@dataclass
class PlotConfig:
    """All parameters that control figure rendering.

    Unit notes
    ----------
    - ``width_pt`` and ``font_size_pt`` are in typographic points (1/72 in).
    - Matplotlib works in inches internally; conversion is applied in the renderer.
    """

    # ── I/O ──────────────────────────────────────────────────────────────────
    input: str = ""
    # Optional secondary CSV for a line chart overlaid on the right y-axis.
    input_line: str = ""
    output: str = "out/figure"          # base path, no extension
    mode: str = "ablation"
    # Output formats to produce in a single run.  Any of: pdf, png, svg, eps.
    formats: List[str] = field(default_factory=lambda: ["pdf", "png"])

    # Y-axis label is read from the CSV value-column header.
    # X-axis group names are read from the CSV 'group' column.
    # No separate label/unit fields are needed for either axis.

    # ── Figure dimensions ────────────────────────────────────────────────────
    width_pt: float = 240.0               # ACM single-column max
    # Height defaults to 240 × (1/φ) ≈ 148 pt for all widths.
    # Single-column (240 pt) therefore keeps the golden rectangle.
    # Wider figures (e.g. 540 pt double-column) stay at the same compact height.
    # Set explicitly to override.
    height_pt: Optional[float] = None

    # ── Typography ───────────────────────────────────────────────────────────
    font_size_pt: float = 7.0             # tick labels and legend — ACM minimum
    font_family: str = "Times New Roman"
    # Axis label font size (y-axis title, x-axis group names).
    # None → font_size_pt + 2 (a visible but modest step up).
    label_font_size_pt: Optional[float] = None

    @property
    def label_font_size(self) -> float:
        if self.label_font_size_pt is not None:
            return self.label_font_size_pt
        return self.font_size_pt + 2.0

    # ── Y-axis ───────────────────────────────────────────────────────────────
    y_ticks: int = 5                      # target number of y-axis ticks
    y_min: Optional[float] = None         # None → auto
    y_max: Optional[float] = None         # None → auto
    right_y_min: Optional[float] = None   # explicit lower bound for an overlaid right axis
    right_y_max: Optional[float] = None   # explicit upper bound for an overlaid right axis
    y_tick_suffix: str = ""
    right_y_tick_suffix: str = ""

    # ── Bar display ──────────────────────────────────────────────────────────
    show_values: bool = False             # print numeric value above each bar
    two_level_xaxis: bool = False         # use major_group/minor_group CSV columns
    panel_cols: int = 1                   # columns for multi-panel ablation/decomp figures
    pair_last_bars: bool = False          # remove the gap between the last two decomp bars
    compact_decomp_legend: bool = False   # encode decomp path hue and stage lightness separately
    compact_decomp_legend_rows: int = 1
    shared_panel_legend: bool = False
    decomp_bar_legend_title: str = "Path"
    decomp_segment_legend_title: str = "Stage"
    show_segment_delta: bool = False      # annotate the upper part of two-segment bars
    segment_delta_mode: str = "percent"  # "percent" | "value"
    segment_delta_decimals: int = 1
    segment_delta_font_size_pt: Optional[float] = None
    show_cumulative_boundaries: bool = False
    cumulative_boundary_decimals: int = 1
    cumulative_boundary_font_size_pt: Optional[float] = None
    decomp_bar_only_legend: bool = False
    decomp_right_bar: str = ""
    decomp_right_y_label: str = ""
    legend_note_first: bool = False       # place decomp legend-note row above data-series rows
    inline_legend_note: bool = False      # append the legend note to the final series label
    parent_label_gap_pt: float = 2.0      # vertical gap between two-level x-axis labels

    # ── Colors ───────────────────────────────────────────────────────────────
    # Custom palette: list of hex/CSS color strings, one per unique label.
    # Leave empty to auto-generate using the golden-ratio darkening algorithm.
    custom_palette: List[str] = field(default_factory=list)
    # Base hue (0–360) for auto-generated palette
    palette_hue: float = 210.0            # cool blue family by default

    # ── Border / spine ───────────────────────────────────────────────────────
    spine_linewidth_pt: float = 1.0

    # ── Computed properties ──────────────────────────────────────────────────
    @property
    def width_in(self) -> float:
        return self.width_pt / PT_PER_INCH

    @property
    def height_in(self) -> float:
        if self.height_pt is not None:
            return self.height_pt / PT_PER_INCH
        # Single-column (≤ 240 pt): compact 120 pt height.
        # Double-column (> 240 pt): golden-ratio height ≈ 148 pt.
        if self.width_pt <= 240.0:
            return _DEFAULT_HEIGHT_SINGLE_PT / PT_PER_INCH
        return _DEFAULT_HEIGHT_WIDE_PT / PT_PER_INCH
