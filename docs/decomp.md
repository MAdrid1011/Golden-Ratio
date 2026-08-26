# Comparison + Decomposition Charts

Decomp mode generates a grouped bar chart where each x-axis group has **n_bars** side-by-side bars for comparison, and each bar can optionally be broken down into stacked segments.  This makes it easy to compare totals across methods/stages while simultaneously showing the contribution of each component.

---

## Quick Example

```bash
# 8 scenes × 2 bars (SPIM solid bar + GPU stacked bar)
# Numeric totals above each bar are always shown automatically.
python main.py --mode decomp \
  --input examples/decomp_pipeline.csv \
  --output out/Decomp_pipeline

# Two-part decomposition with an internal percentage arrow
python main.py --mode decomp \
  --input examples/decomp_pipeline.csv \
  --output out/Decomp_delta \
  --show_segment_delta --segment_delta_mode percent

# Cumulative decomposition with every segment boundary labeled
python main.py --mode decomp \
  --input examples/decomp_pipeline.csv \
  --output out/Decomp_cumulative \
  --show_cumulative_boundaries --decomp_bar_only_legend

# Multiple vertically stacked decomposition panels
python main.py --mode decomp \
  --inputs panel_a.csv panel_b.csv \
  --output out/Decomp_panels
```

---

## CSV Format

Four columns are required, in this order:

```
group, bar, segment, Metric Name
```

| Column | Role |
|--------|------|
| `group` | X-axis group label (e.g. scene name, dataset). |
| `bar` | Bar name within the group — the **comparison** dimension. |
| `segment` | Stack segment name. Leave **empty** for a solid (unsegmented) bar. |
| *(col 4 name)* | Numeric value. The column header becomes the y-axis label. |

Optional columns:

| Column | Role |
|--------|------|
| `major_group` | Parent label for `--two_level_xaxis`. |
| `minor_group` | Child label for `--two_level_xaxis`. |
| `bar_group` | Reserved for grouped bar metadata. |

**Rules**
- Every `(group, bar)` must appear at least once.
- For a segmented bar every group must have the same segments in the same order.
- Unsegmented and segmented bars can coexist within the same chart.

### Unsegmented bars (solid)

Leave the `segment` column empty:

```csv
group,bar,segment,Execution Time (ms)
Scene A,SPIM,,45.2
Scene B,SPIM,,52.7
```

### Segmented (stacked) bars

Provide one row per segment per group:

```csv
group,bar,segment,Execution Time (ms)
Scene A,GPU,Stage 2,12.1
Scene A,GPU,Stage 3,28.4
Scene A,GPU,Stage 4,18.3
Scene B,GPU,Stage 2,14.8
Scene B,GPU,Stage 3,33.1
Scene B,GPU,Stage 4,21.4
```

### Mixed example (one solid bar + one stacked bar per group)

```csv
group,bar,segment,Execution Time (ms)
__caption__,,,(a) Per-scene Pipeline Cost
Sear Steak,Stage 1 (SPIM),,33.7
Sear Steak,GPU Stages,Stage 2,15.2
Sear Steak,GPU Stages,Stage 3,28.4
Sear Steak,GPU Stages,Stage 4,45.1
Sear Steak,GPU Stages,Stage 5,45.1
Coffee Martini,Stage 1 (SPIM),,70.4
Coffee Martini,GPU Stages,Stage 2,22.4
Coffee Martini,GPU Stages,Stage 3,44.8
Coffee Martini,GPU Stages,Stage 4,70.1
Coffee Martini,GPU Stages,Stage 5,69.2
```

### `__caption__` metadata row

```csv
__caption__,,,(a) Per-scene Pipeline Cost
```

Caption text in any non-group column; displayed below the x-axis tick labels, 1 pt larger than the tick-label font.

### `__legend__` metadata row

Use `__legend__` to append a short note to the legend, such as algorithm index mappings.

```csv
__legend__,,,(1) SpecDec++  (2) SVIP
```

---

## Color System

### Comparison bars (one hue per bar)

Each bar position gets a distinct hue chosen for harmony and contrast:

| n_bars | Hues used |
|--------|-----------|
| 1 | 255° blue-violet |
| 2 | 255° blue-violet + 205° sky-blue (analogous cool pair) |
| 3 | + 35° amber (warm triad accent) |
| 4 | + 345° rose (split-complementary warmth) |
| 5 | + 160° teal |
| 6 | + 80° lime |
| > 6 | Evenly distributed across 300° of the hue wheel |

### Segments within a bar (lightness ramp)

All segments share the bar's hue; lightness varies from **dark at the bottom** (L = 0.35) to **light at the top** (L = 0.72), creating a natural depth cue — heavier, more fundamental components appear darker at the base.

---

## Bar Appearance

- Every bar (and every stacked segment) has a **0.5 pt black outline**.
- The **numeric total** of each bar is always displayed above it automatically — no CLI flag required.  The y-axis upper limit is extended dynamically to ensure the label is never clipped by the top spine.

---

## Layout

Spacing follows golden-ratio proportions at every scale:

```
intra-group gap (between bars in same group)  = bar_width / φ  ≈ 0.618
inter-group gap (between groups)              = bar_width × φ  ≈ 1.618
```

**Group separators**
- **n_bars = 2**: no separator — groups are visually distinct from spacing alone.
- **n_bars > 2**: a thin vertical black line is drawn at the midpoint between consecutive groups (same style as ablation charts).

---

## Legend

| Bar type | Legend entry |
|----------|-------------|
| Unsegmented (solid) | One entry per bar with the **bar name** |
| Segmented (stacked) | One entry per **segment name**, in bottom-to-top order |

Entries are arranged in as many columns as fit in a single legend row at the top-right of the chart.

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode decomp` | — | **Required.** |
| `--input CSV` | — | Path to the decomp CSV. |
| `--inputs CSV …` | — | One CSV per vertically stacked panel. |
| `--output PATH` | `out/figure` | Base path (no extension). |
| `--formats fmt …` | `pdf png` | Output formats. |
| `--width_pt` | `240` | Figure width in pt. |
| `--font_size_pt` | `7` | Font size in pt (ACM minimum). |
| `--y_ticks` | `5` | Target number of y-axis ticks. |
| `--y_min` | `0` | Override y-axis lower bound. |
| `--y_max` | *(auto)* | Override y-axis upper bound. |
| `--y_tick_suffix` | empty | Append a suffix such as `%` to left-axis tick labels. |
| `--right_y_tick_suffix` | empty | Append a suffix to right-axis tick labels. |
| `--two_level_xaxis` | off | Use `major_group` and `minor_group` columns for parent/child x-axis labels. |
| `--show_segment_delta` | off | For every two-segment bar, draw a double-headed arrow inside the upper segment. |
| `--segment_delta_mode` | `percent` | Label the upper segment by its percentage of the total or by its absolute `value`. |
| `--segment_delta_decimals` | `1` | Decimal places in the internal delta label. |
| `--segment_delta_font_size_pt` | auto | Requested font size for internal delta labels, capped to fit within the physical bar width. |
| `--show_cumulative_boundaries` | off | Label each stacked-segment boundary with its segment name and cumulative value. |
| `--cumulative_boundary_decimals` | `1` | Decimal places in cumulative boundary labels. |
| `--cumulative_boundary_font_size_pt` | auto | Requested cumulative-label size, capped to fit within the physical bar width. |
| `--decomp_bar_only_legend` | off | Show one legend entry per comparison bar and omit segment entries. |
| `--compact_decomp_legend_rows` | `1` | Keep compact legend dimensions on one row or split them across `2` rows. |
| `--decomp_segment_legend_first` | off | Place the segment legend row above the bar legend row when using two compact rows. |
| `--shared_panel_legend` | off | In a multi-panel decomp figure, draw the common legend only above the first panel. |
| `--decomp_bar_legend_title` | `Path` | Heading for comparison bars in the compact legend. |
| `--decomp_segment_legend_title` | `Stage` | Heading for segments in the compact legend. |
| `--decomp_right_bar` | empty | Render the named comparison bar against a secondary right y-axis. Separate multiple names with commas. |
| `--decomp_right_y_label` | empty | Label for the optional secondary right y-axis. |
| `--pair_bar_groups` | off | Arrange adjacent bars as pairs with a larger gap between each pair. |

---

## Full Working Example

```bash
python main.py --mode decomp \
  --input examples/decomp_pipeline.csv \
  --output out/Decomp_pipeline
# → out/Decomp_pipeline.pdf
# → out/Decomp_pipeline.png
```

The included `decomp_pipeline.csv` recreates an 8-scene pipeline cost chart with 2 bars per scene: a solid SPIM bar and a four-stage stacked GPU bar.
