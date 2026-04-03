# Golden Ratio — ACM Bar Chart Script

A Python plotting tool that generates ACM-compliant bar charts from CSV data.
Every spatial dimension — bar spacing, axis padding, legend layout — is derived
from the golden ratio φ ≈ 1.618, giving figures a coherent visual rhythm without
manual tuning.

---

## Requirements

- Python 3.10+
- matplotlib ≥ 3.7

```bash
pip install -r requirements.txt
```

---

## Quick Start

```bash
# Single-panel figure (240 pt wide, default)
python main.py \
  --input  examples/ablation_example_single.csv \
  --output out/fig_single

# Double-column figure (540 pt wide)
python main.py \
  --input    examples/ablation_example_double.csv \
  --output   out/fig_double \
  --width_pt 540

# Multi-panel figure — three CSVs stacked vertically
python main.py \
  --inputs path/to/panel_a.csv path/to/panel_b.csv path/to/panel_c.csv \
  --output out/fig_multi
```

Each run produces both a PDF and a PNG at the requested output path.

---

## CLI Reference

### Input / Output

| Flag | Description |
|------|-------------|
| `--input CSV` | Path to a **single** bar-chart CSV file. Mutually exclusive with `--inputs`. |
| `--inputs CSV …` | Two or more CSV files rendered as **vertically stacked sub-panels** in one figure. Each CSV may include a `__caption__` metadata row to label its panel. Mutually exclusive with `--input`. |
| `--input_line CSV` | Optional secondary CSV for a **line chart** overlaid on a right y-axis. Uses the same `group`/`label` structure as `--input`. Only applies to single-panel mode. |
| `--output BASEPATH` | Output base path without extension (default: `out/figure`). Extensions are appended automatically for each format. |
| `--formats fmt …` | Space-separated output formats: `pdf`, `png`, `svg`, `eps` (default: `pdf png`). |

### Layout

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `ablation` | Chart mode — currently only `ablation`. |
| `--width_pt` | `240` | Figure width in typographic points. ACM single-column = 240 pt, double-column = 540 pt. |
| `--height_pt` | *(auto)* | Figure height in pt — defaults to `width_pt × (1/φ) ≈ 148 pt` for a single panel; wider figures stay compact at the same height. |

### Typography

| Flag | Default | Description |
|------|---------|-------------|
| `--font_size_pt` | `7` | Tick-label, legend, and axis-label font size in pt (ACM minimum = 7 pt). |
| `--label_font_size_pt` | *(auto)* | Group-name font size — defaults to `font_size_pt + 2`. |

### Axes

| Flag | Default | Description |
|------|---------|-------------|
| `--y_ticks` | `5` | Target number of y-axis ticks. |
| `--y_min` | *(auto)* | Override y-axis lower bound (default: 0 for bar charts). |
| `--y_max` | *(auto)* | Override y-axis upper bound. |
| `--show_values` | off | Print the numeric value above each bar. |

### Color

| Flag | Default | Description |
|------|---------|-------------|
| `--palette_hue` | `210` | Base hue (0–360) for the auto-generated palette. Default 210 = cool blue. |
| `--palette HEX …` | *(auto)* | Custom hex colors, one per unique label in legend order (e.g. `#3A7FC1 #E87D3A`). |

---

## CSV Format

### Single-panel (`--input`)

Three columns are required, in any order:

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

| Column | Description |
|--------|-------------|
| `group` | Group name — shown as the x-axis tick label. Use spaces as word separators so long names can be word-wrapped across two lines. |
| `label` | Variant name within the group — must be **consistent across all groups**; determines bar colors and legend entries. |
| *(any name)* | Numeric measurement. The column header is used verbatim as the y-axis label, including units (e.g. `Speedup (×)`, `F1 Score`). |

#### Optional: subfigure caption

Add a metadata row with `group = __caption__` to attach a panel label below the
x-axis tick labels. The value is read from the same column as the numeric data:

```csv
group,label,FPS Speedup
Sear Steak,H100,2.31
...
__caption__,,(a) 4DGS
```

The caption is rendered 1 pt larger than the tick labels, with 2 pt of padding
from the tick labels above it.

### Multi-panel (`--inputs`)

Each CSV is one panel and follows the same format as above. Panels share the
figure-level color palette and are stacked vertically. Add a `__caption__` row
to each CSV to give that panel a label (e.g. `(a)`, `(b)`, `(c)`).

The axes height of each panel scales to `1/n` of the single-panel height;
decoration (legends, captions, tick labels) adds a fixed overhead per panel so
the total figure height grows gracefully with `n`.

### Secondary line chart (`--input_line`)

Supply a second CSV with the same `group`/`label` column names. Its values are
plotted as a line chart on a right y-axis aligned to the same group centers as
the bars. The right axis is tick-labeled and shares the same tick-count target as
the left axis.

---

## X-Axis Label Behaviour

Group names are word-wrapped adaptively:

- The available width per group cell and the current font size determine the
  maximum characters per line.
- Names that fit on one line are displayed as-is.
- Longer names are split at the best word boundary into **two lines**. When no
  clean break exists, the algorithm tries mid-word hyphenation to keep both lines
  balanced.
- If no two-line fit is found, the algorithm tries a three-line split.
- As a last resort all group labels fall back to circled numerals `①②③…` with a
  mapping row appended to the legend.

When some group names span two lines and others span one line, the one-line
labels are **vertically centred** in the uniform two-line cell using tick padding
(no extra whitespace is introduced below the tick-label area).

---

## ACM Compliance

| Requirement | Implementation |
|-------------|---------------|
| Max width 240 pt | `--width_pt 240` (default) |
| Font ≥ 7 pt, Times New Roman | Enforced by CLI; `rcParams` sets Times New Roman with DejaVu Serif as fallback |
| 1 pt border on all four sides | All spines at 1 pt; `set_clip_on(False)` + `pad_inches = 0.5 pt / 72` ensures equal rendering on every edge |
| Tick marks | Outward on left and bottom only; right side is tick-free unless a secondary line axis is present |

---

## Design: Golden Ratio Throughout

| Element | Rule |
|---------|------|
| Figure height (default) | `width_pt × (1/φ)` — keeps the golden rectangle for the single-column default |
| Bar spacing | boundary→bar edge : inner gap : bar width = `φ/2 : 1/φ : 1` ≈ `0.809 : 0.618 : 1`; all boundaries (spines and separators) are equidistant from their nearest bar |
| Inter-group gap (edge to edge) | `φ × bar_width` — total outer gap : inner gap = `φ² : 1` |
| Y-axis top margin | Fixed 5 pt above the tallest bar |
| Color palette | Linear lightness steps from 0.85 → 0.25 at constant hue and saturation; uniform visual separation across all legend entries |
| Legend internals | swatch side = `font_size × 1.0`; swatch→text gap = `font_size × 0.4`; column gap = `font_size × 0.5` |

---

## Project Structure

```
Golden-Ratio/
├── golden_ratio_plot/
│   ├── __init__.py
│   ├── config.py               # PlotConfig dataclass — all parameters
│   ├── reader.py               # CSV → AblationData typed model
│   ├── renderer/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseRenderer — ACM style, spines, ticks, save
│   │   └── ablation.py         # AblationRenderer — full ablation chart logic
│   └── utils/
│       ├── __init__.py
│       ├── colors.py           # Linear HSL palette generator
│       └── ticks.py            # nice_ticks() / nice_range()
├── examples/
│   ├── ablation_example_single.csv   # Single-column sample (240 pt)
│   └── ablation_example_double.csv   # Double-column sample (540 pt)
├── main.py                     # CLI entry point (argparse)
├── requirements.txt
└── README.md
```

### Extending with a New Chart Mode

1. Create `golden_ratio_plot/renderer/<mode>.py` with a class that inherits from `BaseRenderer`.
2. Implement `_draw(self, fig, ax, data)` — the base class handles style, spines, ticks, and saving.
3. Add the new mode name to `_MODES` in `main.py` and add the corresponding `elif` dispatch branch.
