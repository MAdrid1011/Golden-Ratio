from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec, SubplotSpec
from matplotlib.lines import Line2D

from golden_ratio_plot.config import PT_PER_INCH, PlotConfig
from golden_ratio_plot.renderer.base import BaseRenderer


def _hex(color: str) -> str:
    return color if color else "#4C8DB9"


def _rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _unique(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _as_float(row: Dict[str, str], col: str) -> float:
    return float((row.get(col) or "0").strip())


class ComposeRenderer(BaseRenderer):
    """JSON-driven mixed-panel renderer for paper figures."""

    def _draw(self, fig: Figure, ax: Axes, data: object) -> None:
        return None

    def render_compose(self, json_path: str | Path) -> None:
        cfg = self.config
        path = Path(json_path)
        with path.open(encoding="utf-8") as fh:
            spec = json.load(fh)

        panels = spec.get("panels", [])
        rows = int(spec.get("layout", {}).get("rows", 1))
        cols = int(spec.get("layout", {}).get("cols", 1))
        has_timeline = any(p.get("type") == "timeline" for p in panels)

        height_pt = cfg.height_pt
        if height_pt is None:
            height_pt = 220.0 if has_timeline else 185.0 if rows > 1 else 120.0

        self._apply_rcparams()
        fig = plt.figure(figsize=(cfg.width_pt / PT_PER_INCH, height_pt / PT_PER_INCH))
        grid = GridSpec(rows, cols, figure=fig, hspace=0.72, wspace=0.25)
        base_dir = path.parent

        for panel in panels:
            row = int(panel.get("row", 0))
            col = int(panel.get("col", 0))
            cell = grid[row, col]
            ptype = panel.get("type", "bar")
            if ptype == "timeline":
                self._draw_timeline_panel(fig, cell, panel, base_dir)
                continue

            ax = fig.add_subplot(cell)
            self._configure_spines(ax)
            self._configure_ticks(ax)
            if ptype == "bar":
                self._draw_bar_panel(fig, ax, panel, base_dir)
            elif ptype == "decomp_ratio":
                self._draw_decomp_ratio_panel(fig, ax, panel, base_dir)
            else:
                raise ValueError(f"Unsupported compose panel type: {ptype}")

        if has_timeline:
            fig.subplots_adjust(left=0.12, right=0.94, top=0.92, bottom=0.13, hspace=0.36)
        else:
            fig.subplots_adjust(left=0.10, right=0.94, top=0.90, bottom=0.15, hspace=0.72)
        self._save(fig)
        plt.close(fig)

    # ── Generic bar panel ──────────────────────────────────────────────────

    def _draw_bar_panel(
        self,
        fig: Figure,
        ax: Axes,
        panel: Dict[str, Any],
        base_dir: Path,
    ) -> None:
        data = _rows(base_dir / panel["csv"])
        mode = panel.get("bar_mode", "grouped")
        if mode == "stacked":
            self._draw_stacked_bar(fig, ax, panel, data)
        else:
            self._draw_grouped_bar(fig, ax, panel, data)

    def _draw_grouped_bar(
        self,
        fig: Figure,
        ax: Axes,
        panel: Dict[str, Any],
        data: List[Dict[str, str]],
    ) -> None:
        cfg = self.config
        xspec = panel.get("x", {})
        parent_col = xspec.get("parent_col", "group")
        child_col = xspec.get("child_col", "label")
        parents = _unique(r[parent_col] for r in data)
        children_by_parent = {
            p: _unique(r[child_col] for r in data if r[parent_col] == p)
            for p in parents
        }
        row_map = {(r[parent_col], r[child_col]): r for r in data}
        series = panel.get("series", [])
        colors = panel.get("colors", [])
        layout = panel.get("bar_layout", {})
        bar_w = float(layout.get("bar_width", 0.82))
        intra = float(layout.get("intra_gap", 0.0))
        inter = float(layout.get("inter_gap", 0.82))
        parent_gap = float(layout.get("parent_gap", 1.15))
        outer_gap = float(layout.get("outer_gap", max(inter / 2.0, bar_w / 2.0)))

        centers: Dict[Tuple[str, str, str], float] = {}
        child_centers: List[float] = []
        child_names: List[str] = []
        parent_centers: List[Tuple[str, float]] = []
        boundaries: List[float] = []
        x = 0.0
        first_edge = 0.0
        last_edge = 0.0
        for p_idx, parent in enumerate(parents):
            parent_start = x
            for child in children_by_parent[parent]:
                start = x
                for s_idx, item in enumerate(series):
                    cx = x + bar_w / 2.0
                    centers[(parent, child, item["label"])] = cx
                    x += bar_w
                    if s_idx < len(series) - 1:
                        x += intra
                child_centers.append((start + x) / 2.0)
                child_names.append(child)
                last_edge = x
                x += inter
            parent_end = last_edge
            parent_centers.append((parent, (parent_start + parent_end) / 2.0))
            if p_idx < len(parents) - 1:
                boundaries.append(x + (parent_gap - inter) / 2.0)
            x += parent_gap
        first_edge = 0.0
        x_min = first_edge - outer_gap
        x_max = max(last_edge + outer_gap, 1.0)
        ax.set_xlim(x_min, x_max)

        for p in parents:
            for child in children_by_parent[p]:
                row = row_map[(p, child)]
                for s_idx, item in enumerate(series):
                    label = item["label"]
                    cx = centers[(p, child, label)]
                    ax.bar(
                        cx,
                        _as_float(row, item["column"]),
                        width=bar_w,
                        color=_hex(colors[s_idx] if s_idx < len(colors) else ""),
                        edgecolor="black",
                        linewidth=0.45,
                        zorder=2,
                    )

        self._apply_y_axis(ax, panel.get("y", {}))
        ax.yaxis.grid(True, linestyle="--", linewidth=0.45, color="#D0D0D0", zorder=0)
        ax.set_xticks(child_centers)
        two = panel.get("two_level_xaxis", {})
        child_labels = two.get("child_labels", {})
        parent_labels = two.get("parent_labels", {})
        ax.set_xticklabels(
            [child_labels.get(c, c) for c in child_names],
            fontsize=cfg.font_size_pt,
        )
        ax.tick_params(axis="x", which="both", length=0, pad=1.0)
        if two:
            parent_bottom = _draw_compose_parent_xlabels(
                fig, ax, parent_centers, parent_labels,
                fontsize=cfg.font_size_pt,
            )
            if two.get("boundary_lines", False):
                trans = ax.get_xaxis_transform()
                for bx in [x_min] + boundaries + [x_max]:
                    ax.axvline(bx, color="black", linewidth=0.8, zorder=3, clip_on=False)
                    ax.plot(
                        [bx, bx], [0.0, parent_bottom],
                        transform=trans,
                        color="black",
                        linewidth=0.8,
                        clip_on=False,
                        zorder=3,
                    )

        handles = [
            mpatches.Patch(
                facecolor=_hex(colors[i] if i < len(colors) else ""),
                edgecolor="black",
                linewidth=0.4,
                label=item["label"],
            )
            for i, item in enumerate(series)
        ]
        labels = [item["label"] for item in series]
        self._draw_panel_legend(ax, handles, labels, panel.get("legend", {}))
        self._caption(ax, panel)

    def _draw_stacked_bar(
        self,
        fig: Figure,
        ax: Axes,
        panel: Dict[str, Any],
        data: List[Dict[str, str]],
    ) -> None:
        xspec = panel.get("x", {})
        if "parent_col" in xspec and "child_col" in xspec and "bar_col" in xspec:
            self._draw_grouped_stacked_bar(fig, ax, panel, data)
            return

        cfg = self.config
        xcol = xspec.get("col", "x")
        segments = panel.get("segments", [])
        draw_segments = list(enumerate(segments))
        if panel.get("stack_order") == "reverse":
            draw_segments = list(reversed(draw_segments))
        colors = panel.get("colors", [])
        bar_w = float(panel.get("bar_layout", {}).get("bar_width", 0.76))
        xs = list(range(len(data)))
        for x, row in zip(xs, data):
            bottom = 0.0
            for s_idx, item in draw_segments:
                val = _as_float(row, item["column"])
                ax.bar(
                    x, val, width=bar_w, bottom=bottom,
                    color=_hex(colors[s_idx] if s_idx < len(colors) else ""),
                    edgecolor="black", linewidth=0.4, zorder=2,
                )
                bottom += val

        self._apply_y_axis(ax, panel.get("y", {}))
        ax.yaxis.grid(True, linestyle="--", linewidth=0.45, color="#D0D0D0", zorder=0)
        show_every = panel.get("x", {}).get("show_every", "")
        tick_labels = []
        for row in data:
            label = row[xcol]
            if show_every == "odd" and int(float(label)) % 2 == 0:
                tick_labels.append("")
            else:
                tick_labels.append(label)
        ax.set_xticks(xs)
        ax.set_xticklabels(tick_labels, fontsize=cfg.font_size_pt)
        ax.tick_params(
            axis="x",
            length=0,
            pad=float(panel.get("x", {}).get("tick_pad", -1.0)),
        )
        ax.set_xlim(-0.6, len(data) - 0.4)

        handles = [
            mpatches.Patch(
                facecolor=_hex(colors[i] if i < len(colors) else ""),
                edgecolor="black",
                linewidth=0.4,
                label=item["label"],
            )
            for i, item in enumerate(segments)
        ]
        labels = [item["label"] for item in segments]

        line_spec = panel.get("right_axis_line")
        if line_spec:
            ax2 = ax.twinx()
            ys = [_as_float(row, line_spec["column"]) for row in data]
            ax2.plot(
                xs, ys,
                color=line_spec.get("color", "#e53e3e"),
                linestyle=line_spec.get("linestyle", "--"),
                linewidth=0.8,
                marker=line_spec.get("marker", "o"),
                markersize=2.4,
                markerfacecolor=line_spec.get("markerfacecolor", "white"),
                markeredgecolor=line_spec.get("color", "#e53e3e"),
                zorder=4,
            )
            ax2.set_ylim(line_spec.get("y_min", min(ys)), line_spec.get("y_max", max(ys)))
            ax2.set_yticks(line_spec.get("y_ticks", []))
            ax2.set_ylabel(line_spec.get("label", ""), fontsize=cfg.font_size_pt, labelpad=2)
            ax2.tick_params(axis="y", width=cfg.spine_linewidth_pt, length=3.0, pad=1.2)
            for side in ("top", "bottom", "left"):
                ax2.spines[side].set_visible(False)
            ax2.spines["right"].set_linewidth(cfg.spine_linewidth_pt)
            handles.append(Line2D(
                [], [], color=line_spec.get("color", "#e53e3e"),
                linestyle=line_spec.get("linestyle", "--"),
                marker=line_spec.get("marker", "o"),
                markerfacecolor=line_spec.get("markerfacecolor", "white"),
                markeredgecolor=line_spec.get("color", "#e53e3e"),
                linewidth=0.8,
                markersize=2.4,
            ))
            labels.append(line_spec.get("label", "line"))

        arrow = panel.get("axis_arrow")
        if arrow:
            ax.annotate(
                "",
                xy=(arrow.get("x_end", 1.02), -0.02),
                xytext=(arrow.get("x_start", 0.99), -0.02),
                xycoords=ax.transAxes,
                arrowprops=dict(arrowstyle="-|>", lw=0.8, color="black"),
                clip_on=False,
            )
            ax.text(
                arrow.get("label_x", 1.03), -0.10, arrow.get("label", ""),
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=cfg.font_size_pt,
            )

        self._draw_panel_legend(ax, handles, labels, panel.get("legend", {}))
        self._caption(ax, panel)

    def _draw_grouped_stacked_bar(
        self,
        fig: Figure,
        ax: Axes,
        panel: Dict[str, Any],
        data: List[Dict[str, str]],
    ) -> None:
        cfg = self.config
        xspec = panel.get("x", {})
        parent_col = xspec["parent_col"]
        child_col = xspec["child_col"]
        bar_col = xspec["bar_col"]
        parents = _unique(r[parent_col] for r in data)
        children_by_parent = {
            p: _unique(r[child_col] for r in data if r[parent_col] == p)
            for p in parents
        }
        bars = panel.get("bars") or _unique(r[bar_col] for r in data)
        row_map = {
            (r[parent_col], r[child_col], r[bar_col]): r
            for r in data
        }
        segments = panel.get("segments", [])
        draw_segments = list(enumerate(segments))
        if panel.get("stack_order") == "reverse":
            draw_segments = list(reversed(draw_segments))
        bar_colors = panel.get("bar_segment_colors", {})
        layout = panel.get("bar_layout", {})
        bar_w = float(layout.get("bar_width", 0.76))
        intra = float(layout.get("intra_gap", 0.18))
        inter = float(layout.get("inter_gap", 0.70))
        parent_gap = float(layout.get("parent_gap", 0.95))
        outer_gap = float(layout.get("outer_gap", max(inter / 2.0, bar_w / 2.0)))

        centers: Dict[Tuple[str, str, str], float] = {}
        child_centers: List[float] = []
        child_names: List[str] = []
        parent_centers: List[Tuple[str, float]] = []
        boundaries: List[float] = []
        x = 0.0
        first_edge = 0.0
        last_edge = 0.0
        for p_idx, parent in enumerate(parents):
            parent_start = x
            for child in children_by_parent[parent]:
                start = x
                for b_idx, bar in enumerate(bars):
                    centers[(parent, child, bar)] = x + bar_w / 2.0
                    x += bar_w
                    if b_idx < len(bars) - 1:
                        x += intra
                child_centers.append((start + x) / 2.0)
                child_names.append(child)
                last_edge = x
                x += inter
            parent_centers.append((parent, (parent_start + last_edge) / 2.0))
            if p_idx < len(parents) - 1:
                boundaries.append(x + (parent_gap - inter) / 2.0)
            x += parent_gap
        x_min = first_edge - outer_gap
        x_max = max(last_edge + outer_gap, 1.0)
        ax.set_xlim(x_min, x_max)

        for parent in parents:
            for child in children_by_parent[parent]:
                for bar in bars:
                    row = row_map[(parent, child, bar)]
                    bottom = 0.0
                    colors = bar_colors.get(bar, [])
                    for s_idx, item in draw_segments:
                        val = _as_float(row, item["column"])
                        ax.bar(
                            centers[(parent, child, bar)],
                            val,
                            width=bar_w,
                            bottom=bottom,
                            color=_hex(colors[s_idx] if s_idx < len(colors) else ""),
                            edgecolor="black",
                            linewidth=0.4,
                            zorder=2,
                        )
                        bottom += val

        self._apply_y_axis(ax, panel.get("y", {}))
        ax.yaxis.grid(True, linestyle="--", linewidth=0.45, color="#D0D0D0", zorder=0)
        ax.set_xticks(child_centers)
        two = panel.get("two_level_xaxis", {})
        child_labels = two.get("child_labels", {})
        parent_labels = two.get("parent_labels", {})
        ax.set_xticklabels(
            [child_labels.get(c, c) for c in child_names],
            fontsize=cfg.font_size_pt,
        )
        ax.tick_params(axis="x", which="both", length=0, pad=1.0)
        if two:
            parent_bottom = _draw_compose_parent_xlabels(
                fig, ax, parent_centers, parent_labels,
                fontsize=cfg.font_size_pt,
            )
            if two.get("boundary_lines", False):
                trans = ax.get_xaxis_transform()
                for bx in [x_min] + boundaries + [x_max]:
                    ax.axvline(bx, color="black", linewidth=0.8, zorder=3, clip_on=False)
                    ax.plot(
                        [bx, bx], [0.0, parent_bottom],
                        transform=trans,
                        color="black",
                        linewidth=0.8,
                        clip_on=False,
                        zorder=3,
                    )

        legend = panel.get("legend", {})
        if legend.get("mode") == "bar_segment_rows":
            self._draw_bar_segment_rows_legend(
                ax, bars, segments, bar_colors, legend,
            )
        else:
            handles = [
                mpatches.Patch(
                    facecolor=_hex((panel.get("colors", []) or [])[i] if i < len(panel.get("colors", [])) else ""),
                    edgecolor="black",
                    linewidth=0.4,
                    label=item["label"],
                )
                for i, item in enumerate(segments)
            ]
            self._draw_panel_legend(ax, handles, [s["label"] for s in segments], legend)
        self._caption(ax, panel)

    # ── Decomposition + ratio panel ─────────────────────────────────────────

    def _draw_decomp_ratio_panel(
        self,
        fig: Figure,
        ax: Axes,
        panel: Dict[str, Any],
        base_dir: Path,
    ) -> None:
        cfg = self.config
        data = _rows(base_dir / panel["csv"])
        group_col = "leading_batch"
        obs_col = panel.get("observation_col", "observation")
        seg_cols = panel.get("segments", [])
        seg_labels = panel.get("segment_labels", seg_cols)
        ratio_col = panel.get("ratio_col", "ratio")
        groups = _unique(r[group_col] for r in data)
        colors = ["#AFC8DC", "#BED4E4", "#CDDFEC", "#D9E8F2", "#E5F0F6", "#EFF6FA"]
        bar_w = 0.72
        intra = 0.20
        gap = 0.72
        xs_by_group: Dict[str, List[float]] = {}
        row_by_x: List[Tuple[float, Dict[str, str]]] = []
        centers: List[Tuple[str, float]] = []
        boundaries: List[float] = []
        x = 0.0
        for g_idx, group in enumerate(groups):
            rows = [r for r in data if r[group_col] == group]
            xs: List[float] = []
            start = x
            for row in rows:
                xs.append(x)
                row_by_x.append((x, row))
                x += bar_w + intra
            xs_by_group[group] = xs
            centers.append((group, (start + xs[-1]) / 2.0))
            if g_idx < len(groups) - 1:
                boundaries.append(x - intra / 2.0 + gap / 2.0)
            x += gap

        for xpos, row in row_by_x:
            bottom = 0.0
            total = sum(_as_float(row, c) for c in seg_cols)
            for idx, col in enumerate(seg_cols):
                val = _as_float(row, col)
                ax.bar(
                    xpos, val, width=bar_w, bottom=bottom,
                    color=colors[idx % len(colors)],
                    edgecolor="black", linewidth=0.4, zorder=2,
                )
                bottom += val
            accepted = total * _as_float(row, ratio_col)
            ax.bar(
                xpos, accepted, width=bar_w, bottom=0,
                facecolor=(1, 1, 1, 0), edgecolor="#222222",
                hatch="//////", linewidth=0.0, zorder=3,
            )
            ax.hlines(total, xpos - bar_w / 2, xpos + bar_w / 2,
                      color="black", linestyle="--", linewidth=0.45, zorder=4)

        ax.set_xlim(-0.55, max(x - gap, 1.0) + 0.25)
        ax.set_ylim(0, 16.8)
        ax.set_yticks([0, 4, 8, 12, 16])
        ax.set_ylabel(panel.get("y_label", ""), fontsize=cfg.font_size_pt, labelpad=2)
        ax.yaxis.grid(True, linestyle="--", linewidth=0.45, color="#D0D0D0", zorder=0)
        ax.set_xticks([cx for _, cx in centers])
        ax.set_xticklabels(
            [panel.get("group_format", "Batch={leading_batch}").format(leading_batch=g)
             for g, _ in centers],
            fontsize=cfg.font_size_pt,
        )
        ax.tick_params(axis="x", length=0, pad=1.0)
        for bx in boundaries:
            ax.axvline(bx, color="black", linewidth=0.8, zorder=4)

        ax2 = ax.twinx()
        for group in groups:
            xs = xs_by_group[group]
            rows = [r for r in data if r[group_col] == group]
            ys = [_as_float(r, ratio_col) * 100.0 for r in rows]
            ax2.plot(
                xs, ys, color=panel.get("line_color", "#e53e3e"),
                linestyle="--", linewidth=0.8, marker="o",
                markersize=2.4, markerfacecolor=panel.get("line_color", "#e53e3e"),
                markeredgewidth=0, zorder=5,
            )
        ax2.set_ylim(0, 105)
        ax2.set_yticks([0, 25, 50, 75, 100])
        ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
        ax2.set_ylabel(panel.get("ratio_label", ""), fontsize=cfg.font_size_pt, labelpad=2)
        for side in ("top", "bottom", "left"):
            ax2.spines[side].set_visible(False)
        ax2.spines["right"].set_linewidth(cfg.spine_linewidth_pt)
        ax2.tick_params(axis="y", width=cfg.spine_linewidth_pt, length=3.0, pad=1.2)

        handles = [
            mpatches.Patch(facecolor=colors[i], edgecolor="black", linewidth=0.4)
            for i in range(len(seg_labels))
        ]
        labels = list(seg_labels)
        handles.append(Line2D(
            [], [], color=panel.get("line_color", "#e53e3e"),
            linestyle="--", marker="o", linewidth=0.8, markersize=2.4,
        ))
        labels.append(panel.get("legend_ratio_label", panel.get("ratio_label", "")))
        self._draw_panel_legend(ax, handles, labels, {"ncol": min(7, len(labels))})
        self._caption(ax, panel)

    # ── Timeline panel ──────────────────────────────────────────────────────

    def _draw_timeline_panel(
        self,
        fig: Figure,
        cell: SubplotSpec,
        panel: Dict[str, Any],
        base_dir: Path,
    ) -> None:
        cfg = self.config
        data = _rows(base_dir / panel["csv"])
        sub = cell.subgridspec(2, 1, hspace=0.18)
        axes = [fig.add_subplot(sub[i, 0]) for i in range(2)]
        for ax in axes:
            self._configure_spines(ax)
            self._configure_ticks(ax)
        times = [_as_float(r, panel.get("time_col", "time")) for r in data]
        states = [int(float(r.get(panel.get("state_col", "state"), "0"))) for r in data]
        intervals = self._state_intervals(times, states)

        tracks = panel.get("tracks", [])
        for ax_idx, (ax, track) in enumerate(zip(axes, tracks)):
            yvals = [_as_float(r, track["column"]) for r in data]
            for start, end, active in intervals:
                ax.axvspan(
                    start, end,
                    color=panel.get("active_background" if active else "inactive_background", "#F8F8F8"),
                    zorder=0,
                )
            ax.plot(times, yvals, color=track.get("color", "#164069"), linewidth=0.9, zorder=3)
            ax.fill_between(times, yvals, 0, color=track.get("color", "#164069"),
                            alpha=track.get("fill_alpha", 0.12), zorder=2)
            if track.get("active_fill_color"):
                for start, end, active in intervals:
                    if not active:
                        continue
                    xs = [t for t in times if start <= t <= end]
                    ys = [y for t, y in zip(times, yvals) if start <= t <= end]
                    if xs:
                        ax.fill_between(
                            xs, ys, 0,
                            color=track.get("active_fill_color"),
                            alpha=track.get("active_fill_alpha", 0.35),
                            zorder=2.5,
                        )
            for h in track.get("hlines", []):
                ax.axhline(h["y"], color=h.get("color", "#999999"),
                           alpha=h.get("alpha", 0.6), linewidth=0.6, linestyle="--")
            if track.get("annotate_averages", False):
                for idx, (start, end, active) in enumerate(intervals):
                    if idx == len(intervals) - 1:
                        continue
                    vals = [y for t, y in zip(times, yvals) if start <= t <= end]
                    if not vals:
                        continue
                    avg = sum(vals) / len(vals)
                    color = track.get("active_average_color", "#B23B3B") if active else track.get("color", "#164069")
                    y_text = 86 if active and ax_idx == 1 else 14 if active and ax_idx == 0 else 82
                    ax.text(
                        (start + end) / 2.0, y_text,
                        f"{avg:.0f}%",
                        color=color if active else "#333333",
                        fontsize=cfg.font_size_pt,
                        fontweight="bold" if active else "normal",
                        ha="center",
                        va="center",
                        clip_on=True,
                    )
            yspec = track.get("y", {})
            ax.set_ylim(yspec.get("min", 0), yspec.get("max", 100))
            ax.set_yticks(yspec.get("ticks", [0, 50, 100]))
            ax.set_ylabel(track.get("ylabel", ""), fontsize=cfg.font_size_pt, labelpad=1)
            ax.set_xlim(panel.get("x_min", min(times)), panel.get("x_max", max(times)))
            for start, end, _active in intervals:
                ax.axvline(start, color="black", linestyle=":", linewidth=0.55, zorder=4)
            if intervals:
                ax.axvline(intervals[-1][1], color="black", linestyle=":", linewidth=0.55, zorder=4)
            if ax_idx == 0:
                ax.set_xticklabels([])
                ax.tick_params(axis="x", length=0)
            else:
                ax.set_xticks(panel.get("x_ticks", []))
                labels = panel.get("x_ticklabels", None)
                if labels is not None:
                    ax.set_xticklabels(labels)
                ax.tick_params(axis="x", length=0, pad=1.0)

        handles = [
            Line2D([], [], color=t.get("color", "#164069"), linewidth=0.9)
            for t in tracks
        ]
        labels = [t.get("legend_label", t.get("column", "")) for t in tracks]
        handles.append(mpatches.Patch(facecolor=panel.get("active_background", "#DDE5F0"),
                                      edgecolor="black", linewidth=0.3))
        labels.append(panel.get("legend", {}).get("state_label", "Active"))
        self._draw_panel_legend(axes[0], handles, labels, panel.get("legend", {}))
        axes[-1].set_xlabel(panel.get("caption", ""), fontsize=cfg.font_size_pt + 1, labelpad=0.8)

    @staticmethod
    def _state_intervals(times: List[float], states: List[int]) -> List[Tuple[float, float, int]]:
        if not times:
            return []
        intervals: List[Tuple[float, float, int]] = []
        start = times[0]
        cur = states[0]
        step = (times[1] - times[0]) if len(times) > 1 else 1.0
        for i in range(1, len(times)):
            if states[i] != cur:
                intervals.append((start - step / 2.0, times[i] - step / 2.0, cur))
                start = times[i]
                cur = states[i]
        intervals.append((start - step / 2.0, times[-1] + step / 2.0, cur))
        return intervals

    # ── Shared helpers ──────────────────────────────────────────────────────

    def _apply_y_axis(self, ax: Axes, yspec: Dict[str, Any]) -> None:
        cfg = self.config
        if "min" in yspec and "max" in yspec:
            ax.set_ylim(float(yspec["min"]), float(yspec["max"]))
        if "ticks" in yspec:
            ax.set_yticks(yspec["ticks"])
        if "ticklabels" in yspec:
            ax.set_yticklabels(yspec["ticklabels"])
        ax.set_ylabel(yspec.get("label", ""), fontsize=cfg.font_size_pt, labelpad=2)
        ax.tick_params(axis="y", pad=1.2)

    def _draw_panel_legend(
        self,
        ax: Axes,
        handles: List[Any],
        labels: List[str],
        spec: Dict[str, Any],
    ) -> None:
        cfg = self.config
        order = spec.get("order")
        if order:
            pairs = {label: handle for handle, label in zip(handles, labels)}
            labels = [label for label in order if label in pairs]
            handles = [pairs[label] for label in labels]
        note = spec.get("mapping_note", "")
        if note and spec.get("append_note_to_last", False) and labels:
            estimated = sum(len(label) for label in labels) + len(note) + 4 * len(labels)
            if estimated * cfg.font_size_pt * 0.36 < cfg.width_pt * 0.82:
                labels[-1] = labels[-1] + "  " + note
            else:
                handles.append(Line2D([], [], linestyle="none", color="none"))
                labels.append(note)
        elif note:
            handles.append(Line2D([], [], linestyle="none", color="none"))
            labels.append(note)
        if note and labels and labels[-1] == note:
            ncol = min(len(labels), max(1, int(spec.get("ncol", len(labels))) + 1))
        else:
            ncol = min(int(spec.get("ncol", len(labels))), max(len(labels), 1))
        placement = spec.get("placement", "")
        loc = spec.get("loc", "lower right")
        anchor = spec.get("bbox_to_anchor", [1.0, 1.01])
        if placement == "inside_upper_right":
            loc = "upper right"
            anchor = spec.get("bbox_to_anchor", [0.985, 0.985])
            ncol = int(spec.get("ncol", 1))
        ax.legend(
            handles, labels,
            loc=loc,
            bbox_to_anchor=tuple(anchor),
            ncol=ncol,
            frameon=False,
            fontsize=cfg.font_size_pt,
            handlelength=float(spec.get("handlelength", 1.0)),
            handleheight=float(spec.get("handleheight", 1.0)),
            handletextpad=float(spec.get("handletextpad", 0.35)),
            columnspacing=float(spec.get("columnspacing", 0.35)),
            borderpad=0.0,
            labelspacing=float(spec.get("labelspacing", 0.0)),
            borderaxespad=float(spec.get("borderaxespad", 0.0)),
        )

    def _draw_bar_segment_rows_legend(
        self,
        ax: Axes,
        bars: List[str],
        segments: List[Dict[str, str]],
        bar_colors: Dict[str, List[str]],
        spec: Dict[str, Any],
    ) -> None:
        cfg = self.config
        legends = []
        for row_idx, bar in enumerate(reversed(bars)):
            colors = bar_colors.get(bar, [])
            handles: List[Any] = [
                mpatches.Patch(facecolor="none", edgecolor="none", linewidth=0.0)
            ]
            labels: List[str] = [f"{bar}:"]
            for s_idx, segment in enumerate(segments):
                handles.append(
                    mpatches.Patch(
                        facecolor=_hex(colors[s_idx] if s_idx < len(colors) else ""),
                        edgecolor="black",
                        linewidth=0.4,
                    )
                )
                labels.append(segment["label"])
            leg = ax.legend(
                handles,
                labels,
                loc="lower right",
                bbox_to_anchor=tuple(spec.get("bbox_to_anchor", [1.0, 1.01])),
                ncol=len(labels),
                frameon=False,
                fontsize=cfg.font_size_pt,
                handlelength=1.0,
                handleheight=1.0,
                handletextpad=0.35,
                columnspacing=float(spec.get("columnspacing", 0.35)),
                borderpad=0.0,
                labelspacing=0.0,
                borderaxespad=0.0,
            )
            legends.append(leg)
            if row_idx < len(bars) - 1:
                ax.add_artist(leg)
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()
        ax_height = ax.get_window_extent(renderer).height
        if ax_height <= 0 or not legends:
            return
        row_step = legends[0].get_window_extent(renderer).height / ax_height
        for idx, leg in enumerate(legends):
            leg.set_bbox_to_anchor((1.0, 1.01 + idx * row_step), transform=ax.transAxes)

    def _caption(self, ax: Axes, panel: Dict[str, Any]) -> None:
        caption = panel.get("caption")
        if caption:
            if panel.get("caption_position") == "top_left":
                ax.text(
                    float(panel.get("caption_x", -0.10)),
                    float(panel.get("caption_y", 1.02)),
                    caption,
                    transform=ax.transAxes,
                    ha="left",
                    va="bottom",
                    fontsize=self.config.font_size_pt + 1,
                    fontweight=panel.get("caption_weight", "normal"),
                    clip_on=False,
                )
                return
            ax.set_xlabel(
                caption,
                fontsize=self.config.font_size_pt + 1,
                labelpad=float(panel.get("caption_labelpad", 10.0)),
            )


def _draw_compose_parent_xlabels(
    fig: Figure,
    ax: Axes,
    parent_centers: List[Tuple[str, float]],
    parent_labels: Dict[str, str],
    *,
    fontsize: float,
) -> float:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer)
    tick_labels = [
        lbl for lbl in ax.get_xticklabels()
        if lbl.get_text().strip()
    ]
    fallback_bottom = -0.205
    if axes_bbox.height <= 0 or not tick_labels:
        parent_y = -0.14
        parent_bottom = fallback_bottom
    else:
        child_bottom_px = min(
            lbl.get_window_extent(renderer).y0
            for lbl in tick_labels
        )
        parent_top_px = child_bottom_px - _points_to_pixels(fig, 1.0)
        parent_y = ax.transAxes.inverted().transform(
            (axes_bbox.x0, parent_top_px)
        )[1]
        parent_bottom = fallback_bottom

    trans = ax.get_xaxis_transform()
    parent_texts = []
    for parent, cx in parent_centers:
        parent_texts.append(ax.text(
            cx,
            parent_y,
            parent_labels.get(parent, parent),
            transform=trans,
            ha="center",
            va="top",
            fontsize=fontsize,
            fontweight="normal",
            clip_on=False,
        ))
    if parent_texts and axes_bbox.height > 0:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        axes_bbox = ax.get_window_extent(renderer)
        parent_bottom_px = min(
            text.get_window_extent(renderer).y0
            for text in parent_texts
        ) - _points_to_pixels(fig, 0.5)
        parent_bottom = ax.transAxes.inverted().transform(
            (axes_bbox.x0, parent_bottom_px)
        )[1]
    return parent_bottom


def _points_to_pixels(fig: Figure, points: float) -> float:
    return points * fig.dpi / 72.0
