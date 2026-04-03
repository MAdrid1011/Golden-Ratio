# Ablation Study Charts

Ablation mode generates grouped bar charts that conform to ACM single-column (240 pt) or double-column (540 pt) layout requirements.  All spatial proportions — bar widths, gaps, legend internals — are derived from the golden ratio φ ≈ 1.618.

---

## Quick Examples

```bash
# Single panel, single column (240 pt)
python main.py --input examples/ablation_example_single.csv --output out/fig

# Single panel, double column (540 pt)
python main.py --input examples/ablation_example_double.csv \
               --output out/fig_wide --width_pt 540

# Multi-panel (three panels stacked vertically, one CSV each)
python main.py --inputs examples/ablation_example_single.csv \
                        examples/ablation_example_single.csv \
               --output out/fig_multi

# Bar chart + right-axis line overlay
python main.py --input examples/ablation_example_single.csv \
               --input_line examples/ablation_example_single.csv \
               --output out/fig_line

# Custom palette and 8 y-axis ticks
python main.py --input examples/ablation_example_single.csv \
               --palette "#3A7FC1" "#E87D3A" "#6DBF67" \
               --y_ticks 8 --output out/fig_custom
```

---

## CSV Format

### Minimum required columns

```csv
group,label,Metric Name
```

| Column | Role |
|--------|------|
| `group` | X-axis tick label. Spaces are word-separators for adaptive wrapping (see below). |
| `label` | Variant name (bar color, legend entry). Must be **identical across all groups**. |
| *(any name)* | Numeric measurement. The column header is used verbatim as the y-axis label — include units here, e.g. `FPS`, `PSNR (dB)`, `Speedup (×)`. |

**Example:**

```csv
group,label,Accuracy (%)
Baseline,w/o Attn,82.3
Baseline,w/o Norm,85.1
Baseline,Full,91.4
Encoder,w/o Attn,80.7
Encoder,w/o Norm,83.9
Encoder,Full,89.2
Decoder,w/o Attn,78.5
Decoder,w/o Norm,81.0
Decoder,Full,87.6
```

### Optional metadata rows

Add metadata rows anywhere in the CSV; they are stripped before rendering.

#### `__caption__` — panel subtitle

```csv
__caption__,,(a) Ablation on 4DGS
```

The caption is rendered below the x-axis tick labels, 1 pt larger than the tick-label font, with 2 pt of padding.

---

## Multi-panel (`--inputs`)

Pass one CSV per panel; panels are stacked **vertically** and share the same color palette.

```bash
python main.py --inputs panel_a.csv panel_b.csv panel_c.csv --output out/fig_abc
```

Each panel's bar area height scales to `1/n` of the single-panel bar height so the chart proportions remain consistent.  Fixed decoration (tick labels, axis titles, legends, captions) adds a constant overhead per panel, so the total figure height grows gracefully.

Give each CSV a `__caption__` row to label panels `(a)`, `(b)`, `(c)` …

---

## Right-axis Line Overlay (`--input_line`)

Supply a second CSV whose group/label structure mirrors the primary CSV.  Its numeric column is plotted as a line chart on a **right y-axis** aligned to the same group centers.

```bash
python main.py \
  --input  examples/ablation_example_single.csv \
  --input_line examples/ablation_line_overlay.csv \
  --output out/fig_dual
```

The right axis uses the same tick-count target (`--y_ticks`) as the left axis and is independently scaled to maximise the line variation.

---

## CLI Options (Ablation)

### Input / Output

| Flag | Description |
|------|-------------|
| `--input CSV` | Single-panel CSV. Mutually exclusive with `--inputs`. |
| `--inputs CSV …` | One CSV per panel; panels stacked vertically. Mutually exclusive with `--input`. |
| `--input_line CSV` | Secondary CSV for right-axis line overlay (single-panel only). |
| `--output PATH` | Output base path without extension. Both `.pdf` and `.png` are written by default. |
| `--formats fmt …` | Override output formats: any of `pdf png svg eps`. Default: `pdf png`. |

### Layout

| Flag | Default | Description |
|------|---------|-------------|
| `--width_pt` | `240` | Figure width in typographic points. ACM single-column = 240 pt, double-column = 540 pt. |
| `--height_pt` | *(auto)* | Explicit figure height in pt. Defaults to `width_pt / φ` for a single panel. |

### Typography

| Flag | Default | Description |
|------|---------|-------------|
| `--font_size_pt` | `7` | Tick-label, legend, and axis-label font size in pt. ACM minimum is 7 pt. |
| `--label_font_size_pt` | `font_size_pt + 2` | Group-name (x-axis tick label) font size in pt. |

### Axes

| Flag | Default | Description |
|------|---------|-------------|
| `--y_ticks` | `5` | Target number of y-axis ticks. The axis engine rounds to the nearest "nice" step. |
| `--y_min` | `0` | Override y-axis lower bound. |
| `--y_max` | *(auto)* | Override y-axis upper bound. |
| `--show_values` | off | Print the numeric value above each bar. |

### Color

| Flag | Default | Description |
|------|---------|-------------|
| `--palette_hue` | `210` | Base hue (0–360°) for the auto-generated palette. Default 210 = cool blue. |
| `--palette HEX …` | *(auto)* | Explicit hex colors, one per legend entry in order (e.g. `#3A7FC1 #E87D3A`). |

---

## X-Axis Label Wrapping

Group names are wrapped automatically to fit the available cell width:

1. **One line** — label fits as-is.
2. **Two lines** — split at the best word boundary; if no clean break exists the algorithm tries mid-word hyphenation to balance both halves.
3. **Three lines** — attempted when no two-line fit is found.
4. **Circled numerals** `①②③…` — last resort when no text wrap works; a mapping legend row is appended.

When some labels span two lines and others span one, the one-line labels are **vertically centred** in the two-line cell using tick padding — no blank line is inserted below the tick-label area.

---

## ACM Compliance Checklist

| Requirement | How it is met |
|-------------|---------------|
| Max width ≤ 240 pt (single column) | `--width_pt 240` (default) |
| Font size ≥ 7 pt | CLI validation; `rcParams` sets Times New Roman (DejaVu Serif as fallback) |
| 1 pt border on all four sides | All spines at 1 pt weight; equal padding on every edge |
| Tick marks outward | Left and bottom only; right side is tick-free unless `--input_line` is used |

---

## Color Palette Details

Without `--palette`, colors are generated with linear lightness steps from L = 0.85 (lightest) to L = 0.25 (darkest) at a fixed hue and saturation, ensuring uniform perceptual separation across all legend entries.

```bash
# Warm orange base hue
python main.py --input examples/ablation_example_single.csv \
               --palette_hue 30 --output out/fig_warm

# Fully custom colors (one hex per label, in legend order)
python main.py --input examples/ablation_example_single.csv \
               --palette "#D62728" "#1F77B4" "#2CA02C" \
               --output out/fig_custom
```
