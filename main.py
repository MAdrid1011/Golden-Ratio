#!/usr/bin/env python3
"""CLI entry point for golden_ratio_plot.

Usage
-----
    python main.py --input examples/ablation_example_single.csv --output out/fig_single
    python main.py --input examples/ablation_example_double.csv --output out/fig_double --width_pt 540

The y-axis label is taken directly from the CSV value-column header.
Write the unit into the header when needed, e.g. ``Accuracy (%)``.
"""

from __future__ import annotations

import argparse
import sys

from golden_ratio_plot.config import PlotConfig
from golden_ratio_plot.reader import read_csv, read_decomp_csv, read_sensitivity_csv
from golden_ratio_plot.renderer.ablation import AblationRenderer
from golden_ratio_plot.renderer.compose import ComposeRenderer
from golden_ratio_plot.renderer.decomp import DecompRenderer
from golden_ratio_plot.renderer.sensitivity import SensitivityRenderer

_MODES = ("ablation", "decomp", "sensitivity", "compose")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="golden_ratio_plot",
        description="Render ACM-compliant bar charts from a CSV file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ── I/O ──────────────────────────────────────────────────────────────────
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", metavar="CSV",
                   help="Path to a single bar-chart CSV file.")
    g.add_argument("--inputs", nargs="+", metavar="CSV",
                   help="Two or more CSV files to render as vertically stacked "
                        "sub-panels in one figure.  Each CSV may contain a "
                        "``__caption__`` metadata row for its panel label.")
    p.add_argument("--input_line", default="", metavar="CSV",
                   help="Optional path to a secondary CSV for a line chart on "
                        "the right y-axis.  Same group/label structure as --input.")
    p.add_argument("--input_lines", nargs="+", default=[], metavar="CSV",
                   help="One line-chart CSV per panel (matches order of --inputs). "
                        "Use '' as a placeholder to skip the line for a specific panel.")
    p.add_argument("--output", default="out/figure", metavar="BASEPATH",
                   help="Output base path without extension (e.g. out/fig1).")
    p.add_argument("--formats", nargs="+", default=["pdf", "png"],
                   metavar="FMT",
                   help="Output formats to produce (default: pdf png).")
    p.add_argument("--mode", default="ablation", choices=_MODES,
                   help="Chart mode.")

    # Both axis labels come from the CSV:
    #   y-axis → value-column header (e.g. "Accuracy (%)")
    #   x-axis → 'group' column values shown as tick labels

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
    p.add_argument("--two_level_xaxis", action="store_true",
                   help="Use major_group/minor_group CSV columns for two-level x-axis labels.")
    p.add_argument("--panel_cols", type=int, default=1,
                   help="Number of columns for multi-panel ablation/decomp figures.")
    p.add_argument("--font_size_pt", type=float, default=7.0,
                   help="Tick-label and legend font size in pt (ACM minimum: 7).")
    p.add_argument("--label_font_size_pt", type=float, default=None,
                   help="Axis-label font size in pt (default: font_size_pt + 2).")

    # ── Color ─────────────────────────────────────────────────────────────────
    p.add_argument("--palette_hue", type=float, default=210.0,
                   help="Base hue (0–360) for auto-generated color palette.")
    p.add_argument("--palette", nargs="+", default=[], metavar="HEX",
                   help="Custom hex colors, one per unique label (e.g. #3A7FC1).")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _min_fs = 6.0 if args.mode == "sensitivity" else 7.0
    if args.font_size_pt < _min_fs:
        parser.error(
            f"--font_size_pt must be ≥ {_min_fs} for this mode (got {args.font_size_pt})."
        )

    config = PlotConfig(
        input=args.input or "",
        input_line=args.input_line,
        output=args.output,
        formats=args.formats,
        mode=args.mode,
        width_pt=args.width_pt,
        height_pt=args.height_pt,
        font_size_pt=args.font_size_pt,
        label_font_size_pt=args.label_font_size_pt,
        y_ticks=args.y_ticks,
        y_min=args.y_min,
        y_max=args.y_max,
        show_values=args.show_values,
        two_level_xaxis=args.two_level_xaxis,
        panel_cols=max(1, args.panel_cols),
        palette_hue=args.palette_hue,
        custom_palette=args.palette,
    )

    if config.mode == "ablation":
        renderer = AblationRenderer(config)
        if args.inputs:
            datasets = [read_csv(f) for f in args.inputs]
            line_datasets = None
            if args.input_lines:
                line_datasets = [
                    read_csv(p) if p else None
                    for p in args.input_lines
                ]
            renderer.render_panels(datasets, line_datasets=line_datasets)
        else:
            data = read_csv(config.input)
            renderer.render(data)

    elif config.mode == "decomp":
        renderer = DecompRenderer(config)
        if args.inputs:
            datasets = [read_decomp_csv(f) for f in args.inputs]
            renderer.render_panels(datasets)
        else:
            data = read_decomp_csv(config.input)
            renderer.render(data)

    elif config.mode == "sensitivity":
        renderer = SensitivityRenderer(config)
        if args.inputs:
            datasets = [read_sensitivity_csv(f) for f in args.inputs]
        else:
            datasets = [read_sensitivity_csv(config.input)]
        renderer.render_sensitivity(datasets)

    elif config.mode == "compose":
        if args.inputs:
            parser.error("--mode compose expects a single --input JSON file.")
        renderer = ComposeRenderer(config)
        renderer.render_compose(config.input)

    else:
        print(f"Unknown mode: {config.mode!r}", file=sys.stderr)
        return 1

    for path in getattr(renderer, "_saved_paths", [config.output]):  # type: ignore[union-attr]
        print(f"Saved → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
