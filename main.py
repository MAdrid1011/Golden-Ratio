#!/usr/bin/env python3
"""CLI entry point for golden_ratio_plot.

Usage
-----
    python main.py --input examples/ablation_example.csv \\
                   --output out/fig1 \\
                   --mode ablation \\
                   --show_values

The y-axis label is taken directly from the CSV value-column header.
Write the unit into the header when needed, e.g. ``Accuracy (%)``.
"""

from __future__ import annotations

import argparse
import sys

from golden_ratio_plot.config import PlotConfig
from golden_ratio_plot.reader import read_csv
from golden_ratio_plot.renderer.ablation import AblationRenderer

_MODES = ("ablation",)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="golden_ratio_plot",
        description="Render ACM-compliant bar charts from a CSV file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ── I/O ──────────────────────────────────────────────────────────────────
    p.add_argument("--input", required=True, metavar="CSV",
                   help="Path to the input CSV file.")
    p.add_argument("--output", default="out/figure", metavar="BASEPATH",
                   help="Output base path without extension (e.g. out/fig1).")
    p.add_argument("--formats", nargs="+", default=["pdf", "png"],
                   metavar="FMT",
                   help="Output formats to produce (default: pdf png).")
    p.add_argument("--mode", default="ablation", choices=_MODES,
                   help="Chart mode.")

    # ── Axis labels ──────────────────────────────────────────────────────────
    p.add_argument("--x_label", default="Configuration",
                   help="X-axis variable name (shown as tick labels).")
    p.add_argument("--x_unit", default=None,
                   help="X-axis unit (omit if not meaningful).")
    # Y-axis label is read from the CSV value-column header; no CLI arg needed.

    # ── Figure size ───────────────────────────────────────────────────────────
    p.add_argument("--width_pt", type=float, default=240.0,
                   help="Figure width in typographic points (1 pt = 1/72 in).")
    p.add_argument("--height_pt", type=float, default=None,
                   help="Figure height in pt. Defaults to width × 0.618 (golden rectangle).")

    # ── Y-axis control ────────────────────────────────────────────────────────
    p.add_argument("--y_ticks", type=int, default=5,
                   help="Target number of y-axis ticks.")
    p.add_argument("--y_min", type=float, default=None,
                   help="Override y-axis minimum.")
    p.add_argument("--y_max", type=float, default=None,
                   help="Override y-axis maximum.")

    # ── Display options ───────────────────────────────────────────────────────
    p.add_argument("--show_values", action="store_true",
                   help="Print numeric values on top of each bar.")
    p.add_argument("--font_size_pt", type=float, default=7.0,
                   help="Base font size in pt (must be ≥ 7 for ACM compliance).")

    # ── Color ─────────────────────────────────────────────────────────────────
    p.add_argument("--palette_hue", type=float, default=210.0,
                   help="Base hue (0–360) for auto-generated color palette.")
    p.add_argument("--palette", nargs="+", default=[], metavar="HEX",
                   help="Custom hex colors, one per unique label (e.g. #3A7FC1).")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.font_size_pt < 7.0:
        parser.error(
            f"--font_size_pt must be ≥ 7 for ACM compliance (got {args.font_size_pt})."
        )

    config = PlotConfig(
        input=args.input,
        output=args.output,
        formats=args.formats,
        mode=args.mode,
        x_label=args.x_label,
        x_unit=args.x_unit,
        width_pt=args.width_pt,
        height_pt=args.height_pt,
        font_size_pt=args.font_size_pt,
        y_ticks=args.y_ticks,
        y_min=args.y_min,
        y_max=args.y_max,
        show_values=args.show_values,
        palette_hue=args.palette_hue,
        custom_palette=args.palette,
    )

    data = read_csv(config.input)

    if config.mode == "ablation":
        renderer = AblationRenderer(config)
    else:
        print(f"Unknown mode: {config.mode!r}", file=sys.stderr)
        return 1

    renderer.render(data)
    for path in getattr(renderer, "_saved_paths", [config.output]):
        print(f"Saved → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
