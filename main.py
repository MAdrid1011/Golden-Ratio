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
    p.add_argument("--right_y_min", type=float, default=None,
                   help="Override the lower bound of an overlaid right y-axis.")
    p.add_argument("--right_y_max", type=float, default=None,
                   help="Override the upper bound of an overlaid right y-axis.")
    p.add_argument("--y_tick_suffix", default="",
                   help="Suffix appended to left y-axis tick labels.")
    p.add_argument("--right_y_tick_suffix", default="",
                   help="Suffix appended to right y-axis tick labels.")

    # ── Display options ───────────────────────────────────────────────────────
    p.add_argument("--show_values", action="store_true",
                   help="Print numeric values on top of each bar.")
    p.add_argument("--two_level_xaxis", action="store_true",
                   help="Use major_group/minor_group CSV columns for two-level x-axis labels.")
    p.add_argument("--panel_cols", type=int, default=1,
                   help="Number of columns for multi-panel ablation/decomp figures.")
    p.add_argument("--pair_last_bars", action="store_true",
                   help="Remove the gap between the last two bars in each decomp group.")
    p.add_argument("--compact_decomp_legend", action="store_true",
                   help="Use a compact path-hue and stage-lightness legend for decomp charts.")
    p.add_argument("--compact_decomp_legend_rows", type=int, choices=(1, 2),
                   default=1,
                   help="Place compact decomp legend dimensions on one row or "
                        "on separate rows.")
    p.add_argument("--shared_panel_legend", action="store_true",
                   help="For multi-panel decomp charts, keep the legend only "
                        "above the first panel.")
    p.add_argument("--decomp_bar_legend_title", default="Path",
                   help="Heading for comparison bars in a compact decomp legend.")
    p.add_argument("--decomp_segment_legend_title", default="Stage",
                   help="Heading for stacked segments in a compact decomp legend.")
    p.add_argument("--show_segment_delta", action="store_true",
                   help="For two-segment decomp bars, draw an internal double-headed "
                        "arrow spanning the upper segment and label its size.")
    p.add_argument("--segment_delta_mode", choices=("percent", "value"),
                   default="percent",
                   help="Show the upper segment as a percentage of the total bar "
                        "or as an absolute value.")
    p.add_argument("--segment_delta_decimals", type=int, default=1,
                   help="Decimal places used by internal segment-delta labels.")
    p.add_argument("--segment_delta_font_size_pt", type=float, default=None,
                   help="Font size for internal segment-delta labels. The renderer "
                        "also caps it to fit within the physical bar width.")
    p.add_argument("--show_cumulative_boundaries", action="store_true",
                   help="Label every stacked-segment boundary with its segment "
                        "name and cumulative value.")
    p.add_argument("--cumulative_boundary_decimals", type=int, default=1,
                   help="Decimal places used by cumulative boundary labels.")
    p.add_argument("--cumulative_boundary_font_size_pt", type=float, default=None,
                   help="Font size for cumulative boundary labels. The renderer "
                        "also caps it to fit within the physical bar width.")
    p.add_argument("--decomp_bar_only_legend", action="store_true",
                   help="Show one legend entry per comparison bar and omit "
                        "stacked-segment entries.")
    p.add_argument("--decomp_right_bar", default="",
                   help="Render the named decomp bar against a secondary right y-axis.")
    p.add_argument("--decomp_right_y_label", default="",
                   help="Right-axis label used with --decomp_right_bar.")
    p.add_argument("--legend_note_first", action="store_true",
                   help="Place the decomp legend-note row above the data-series legend rows.")
    p.add_argument("--inline_legend_note", action="store_true",
                   help="Append the decomp legend note to the final series label.")
    p.add_argument("--parent_label_gap_pt", type=float, default=2.0,
                   help="Gap in pt between minor and major labels on a two-level x-axis.")
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
        right_y_min=args.right_y_min,
        right_y_max=args.right_y_max,
        y_tick_suffix=args.y_tick_suffix,
        right_y_tick_suffix=args.right_y_tick_suffix,
        show_values=args.show_values,
        two_level_xaxis=args.two_level_xaxis,
        panel_cols=max(1, args.panel_cols),
        pair_last_bars=args.pair_last_bars,
        compact_decomp_legend=args.compact_decomp_legend,
        compact_decomp_legend_rows=args.compact_decomp_legend_rows,
        shared_panel_legend=args.shared_panel_legend,
        decomp_bar_legend_title=args.decomp_bar_legend_title,
        decomp_segment_legend_title=args.decomp_segment_legend_title,
        show_segment_delta=args.show_segment_delta,
        segment_delta_mode=args.segment_delta_mode,
        segment_delta_decimals=max(0, args.segment_delta_decimals),
        segment_delta_font_size_pt=args.segment_delta_font_size_pt,
        show_cumulative_boundaries=args.show_cumulative_boundaries,
        cumulative_boundary_decimals=max(0, args.cumulative_boundary_decimals),
        cumulative_boundary_font_size_pt=args.cumulative_boundary_font_size_pt,
        decomp_bar_only_legend=args.decomp_bar_only_legend,
        decomp_right_bar=args.decomp_right_bar,
        decomp_right_y_label=args.decomp_right_y_label,
        legend_note_first=args.legend_note_first,
        inline_legend_note=args.inline_legend_note,
        parent_label_gap_pt=args.parent_label_gap_pt,
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
