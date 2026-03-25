from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

PHI = 1.6180339887  # golden ratio
PT_PER_INCH = 72.0

# Default figure height = single-column width × (1/φ).
# Wide figures (e.g. double-column) share this same height so they stay compact.
_DEFAULT_HEIGHT_PT = 240.0 / PHI   # ≈ 148.3 pt


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

    # ── Bar display ──────────────────────────────────────────────────────────
    show_values: bool = False             # print numeric value above each bar

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
        return _DEFAULT_HEIGHT_PT / PT_PER_INCH  # fixed ≈ 148 pt for all widths

