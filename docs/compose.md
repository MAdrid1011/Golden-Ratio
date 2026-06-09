# Compose Figures

Compose mode builds a multi-panel figure from a JSON specification. It reuses the same ACM typography, spine width, palette handling, and output path logic as the CSV-only modes, while allowing different panel types in one figure.

```bash
python main.py --mode compose \
  --input examples/compose_two_panel.json \
  --output out/Compose_two_panel --formats pdf png svg
```

The JSON file is the only input passed to `--input`. CSV paths inside the JSON are resolved relative to the JSON file.

---

## JSON Structure

```json
{
  "layout": { "rows": 2, "cols": 1 },
  "panels": [
    { "row": 0, "col": 0, "type": "bar", "csv": "compose_grouped.csv" },
    { "row": 1, "col": 0, "type": "bar", "csv": "compose_stacked.csv" }
  ]
}
```

| Key | Description |
|-----|-------------|
| `layout.rows`, `layout.cols` | Grid shape for the figure. |
| `panels` | List of panel specifications. |
| `row`, `col` | Zero-based panel position in the grid. |
| `type` | One of `bar`, `decomp_ratio`, or `timeline`. |
| `csv` | Panel data file, relative to the JSON file. |

Use the usual global CLI options for figure width, font size, y-axis defaults, palette, and output formats.

---

## Bar Panel

A `bar` panel supports grouped bars and stacked bars. Grouped bars use one row per x position and one numeric column per series.

```json
{
  "type": "bar",
  "bar_mode": "grouped",
  "csv": "compose_grouped.csv",
  "x": { "parent_col": "model", "child_col": "algorithm" },
  "series": [
    { "label": "NPU", "column": "NPU" },
    { "label": "PIM", "column": "PIM" }
  ],
  "two_level_xaxis": {
    "boundary_lines": true
  },
  "y": {
    "label": "Stall Ratio (%)",
    "min": 0,
    "max": 100,
    "ticks": [0, 25, 50, 75, 100]
  },
  "caption": "(a)"
}
```

CSV:

```csv
model,algorithm,NPU,PIM
OPT,SpecDec++,43,34
OPT,SVIP,48,38
LLaMA2,SpecDec++,51,31
LLaMA2,SVIP,46,36
```

For stacked bars, set `"bar_mode": "stacked"` and list `segments` instead of `series`. A `right_axis_line` object can overlay a dashed line on a secondary y-axis.

Legends are placed above the axes by default. For compact panels, set
`"legend": { "placement": "inside_upper_right", "ncol": 1 }` to place a
top-to-bottom legend inside the upper-right corner of the plotting area.
For stacked bars, `"x": { "tick_pad": 2 }` can be used to increase the
distance between the x-axis tick labels and the axis line.

---

## Decomposition-Ratio Panel

`decomp_ratio` draws stacked cumulative bars, an accepted-region hatch, group separators, and a right-axis ratio line. It is intended for figures that compare composition and acceptance in the same panel.

Required CSV columns are:

| Column | Description |
|--------|-------------|
| `leading_batch` | Group name. |
| `observation` | Observation index within the group. |
| segment columns | One numeric column per stacked segment. |
| ratio column | Acceptance ratio in `[0, 1]`. |

JSON:

```json
{
  "type": "decomp_ratio",
  "csv": "compose_decomp_ratio.csv",
  "segments": ["b1", "b2", "b3", "b4"],
  "segment_labels": ["1st", "2nd", "3rd", "4th"],
  "ratio_col": "accept_ratio",
  "y_label": "Cumulative Draft",
  "ratio_label": "Acceptance Ratio (%)",
  "group_format": "Batch={leading_batch}",
  "caption": "(b)"
}
```

---

## Timeline Panel

`timeline` draws two stacked utilization tracks. It supports state-background intervals, line traces, fill-between shading, threshold lines, and interval-average annotations.

```json
{
  "type": "timeline",
  "csv": "compose_timeline.csv",
  "time_col": "time",
  "state_col": "pim_active",
  "tracks": [
    {
      "column": "npu_util",
      "ylabel": "NPU (%)",
      "legend_label": "NPU",
      "color": "#315A7D",
      "active_fill_color": "#F0A0A0",
      "annotate_averages": true,
      "y": { "min": 0, "max": 100, "ticks": [0, 50, 100] }
    },
    {
      "column": "pim_util",
      "ylabel": "PIM (%)",
      "legend_label": "PIM",
      "color": "#4B8A6B",
      "annotate_averages": true,
      "y": { "min": 0, "max": 100, "ticks": [0, 50, 100] }
    }
  ],
  "legend": { "state_label": "PIM active", "ncol": 3 },
  "caption": "(a)"
}
```

CSV:

```csv
time,pim_active,npu_util,pim_util
0,0,78,12
1,0,80,15
2,1,55,74
3,1,43,86
4,0,76,18
```

---

## Examples

| File | Purpose |
|------|---------|
| `examples/compose_two_panel.json` | Grouped two-level bars plus stacked bars with a right-axis line. |
| `examples/compose_timeline.json` | Two-track utilization timeline with active-window annotations. |
