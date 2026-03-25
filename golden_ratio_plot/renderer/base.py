from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from golden_ratio_plot.config import PlotConfig

# Use the non-interactive Agg backend so the script works headlessly.
matplotlib.use("Agg")


class BaseRenderer(ABC):
    """Abstract base class that applies ACM typographic constraints.

    Subclasses implement :meth:`_draw` which receives a fully configured
    ``(fig, ax)`` pair and should populate it without touching global rcParams
    or spine/tick settings (those are handled here).
    """

    def __init__(self, config: PlotConfig) -> None:
        self.config = config

    # ── Public API ────────────────────────────────────────────────────────────

    def render(self, data: object) -> None:
        """Build the figure, call the subclass draw method, and save."""
        self._apply_rcparams()
        fig, ax = self._make_figure()
        self._configure_spines(ax)
        self._configure_ticks(ax)
        self._draw(fig, ax, data)
        self._save(fig)
        plt.close(fig)

    # ── Abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    def _draw(self, fig: Figure, ax: Axes, data: object) -> None:
        """Subclass-specific drawing logic."""

    # ── Style setup ──────────────────────────────────────────────────────────

    def _apply_rcparams(self) -> None:
        cfg = self.config
        plt.rcParams.update(
            {
                "font.family": "serif",
                "font.serif": [cfg.font_family, "DejaVu Serif", "serif"],
                "font.size": cfg.font_size_pt,
                "axes.labelsize": cfg.font_size_pt,
                "xtick.labelsize": cfg.font_size_pt,
                "ytick.labelsize": cfg.font_size_pt,
                "legend.fontsize": cfg.font_size_pt,
                "pdf.fonttype": 42,   # embed fonts as Type 1 → PDF/X compatible
                "ps.fonttype": 42,
                "figure.dpi": 300,
                "savefig.dpi": 300,
            }
        )

    def _make_figure(self) -> Tuple[Figure, Axes]:
        cfg = self.config
        fig, ax = plt.subplots(figsize=(cfg.width_in, cfg.height_in))
        return fig, ax

    def _configure_spines(self, ax: Axes) -> None:
        """Ensure all four spines are visible at 1 pt width.

        ``set_clip_on(False)`` is required so that the full line width is
        rendered.  Without it, each spine is clipped to the axes bounding box:
        the spine line is centered on the boundary, so half the line width
        falls outside the clip region and the saved figure shows only 0.5 pt
        instead of 1 pt — most visibly on the right spine where there are no
        outward tick marks to mask the effect.
        """
        cfg = self.config
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(cfg.spine_linewidth_pt)
            spine.set_clip_on(False)

    def _configure_ticks(self, ax: Axes) -> None:
        """Set tick direction outward; only left and bottom carry tick marks."""
        cfg = self.config
        ax.tick_params(
            axis="both", which="major",
            direction="out",
            width=cfg.spine_linewidth_pt,
            length=3.0,
            top=False,
            right=False,
            left=True,
            bottom=True,
        )
        ax.tick_params(
            axis="both", which="minor",
            direction="out",
            width=cfg.spine_linewidth_pt * 0.618,
            length=2.0,
            top=False,
            right=False,
            left=True,
            bottom=True,
        )

    # ── Output ────────────────────────────────────────────────────────────────

    def _save(self, fig: Figure) -> None:
        """Save the figure in every format listed in ``config.formats``.

        ``config.output`` is treated as a base path (extension is stripped if
        present so that adding ``.pdf`` / ``.png`` always works correctly).
        """
        cfg = self.config
        base = Path(cfg.output)
        # Strip any existing extension so the base is always clean.
        if base.suffix.lower().lstrip(".") in {"pdf", "png", "svg", "eps"}:
            base = base.with_suffix("")
        base.parent.mkdir(parents=True, exist_ok=True)

        # pad_inches = half the spine linewidth (in inches).
        # bbox_inches='tight' computes the bounding box from drawn content; without
        # this pad the outer half of the right spine (which has no outward ticks to
        # extend the bbox) is outside the saved boundary and appears as 0.5 pt.
        from golden_ratio_plot.config import PT_PER_INCH
        pad = cfg.spine_linewidth_pt / 2.0 / PT_PER_INCH

        saved: list[str] = []
        for fmt in cfg.formats:
            out = base.with_suffix(f".{fmt.lower()}")
            fig.savefig(str(out), format=fmt.lower(),
                        bbox_inches="tight", pad_inches=pad)
            saved.append(str(out))
        # Store the list for the caller to print.
        self._saved_paths = saved
