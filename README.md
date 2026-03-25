# Golden Ratio — ACM Bar Chart Script

A Python plotting tool that generates ACM-compliant bar charts from CSV data.
Every spatial dimension — bar spacing, axis padding, color progression, legend
layout — is derived from the golden ratio φ ≈ 1.618, giving the figures a
coherent visual rhythm without manual tuning.

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
python main.py \
  --input  examples/ablation_example.csv \
  --output out/fig1 \
  --show_values
```

This produces `out/fig1.pdf` **and** `out/fig1.png` in one run.

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | *(required)* | Path to the input CSV file |
| `--output` | `out/figure` | Output base path — no extension needed |
| `--formats` | `pdf png` | Space-separated list of output formats (`pdf`, `png`, `svg`, `eps`) |
| `--mode` | `ablation` | Chart mode — currently only `ablation` |
| `--x_label` | `Configuration` | X-axis variable name (displayed on tick labels; no axis title is shown) |
| `--x_unit` | *(none)* | X-axis unit — omit if the unit is not meaningful (e.g. "个") |
| `--width_pt` | `240` | Figure width in typographic points (ACM single-column max = 240 pt) |
| `--height_pt` | *(auto)* | Figure height in pt — defaults to `width × 0.618` (golden rectangle) |
| `--font_size_pt` | `7` | Base font size in pt (ACM minimum = 7 pt) |
| `--y_ticks` | `5` | Target number of y-axis ticks |
| `--y_min` | *(auto)* | Override y-axis lower bound |
| `--y_max` | *(auto)* | Override y-axis upper bound |
| `--show_values` | off | Print numeric value above each bar |
| `--palette_hue` | `210` | Base hue (0–360) for the auto-generated color palette |
| `--palette HEX …` | *(auto)* | Custom hex colors, one per unique label (e.g. `#3A7FC1`) |

---

## CSV Format

### Ablation mode (`--mode ablation`)

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
| `group` | Ablation group name — shown as the x-axis tick label |
| `label` | Variant name within the group — must be **consistent across all groups**; determines legend entries and bar colors |
| *(any name)* | Numeric measurement — the column header is used verbatim as the y-axis label. Write the unit directly in the header when needed, e.g. `Accuracy (%)`, `Speedup (×)`, `F1 Score`. |

**Rules**

- Every `(group, label)` pair must be unique.
- The order rows appear in the CSV determines the display order of groups and labels.
- If any group name exceeds 12 characters, all group labels are replaced with `(1)`, `(2)`, … on the x-axis and the mapping is appended to the legend.

---

## ACM Compliance

| Requirement | Implementation |
|-------------|---------------|
| Max width 240 pt | `--width_pt 240` (default) |
| Font ≥ 7 pt, Times New Roman | Enforced by CLI; `rcParams` sets Times New Roman |
| 1 pt border on all four sides | All spines at 1 pt; `set_clip_on(False)` + `pad_inches = 0.5/72"` ensures equal rendering on every edge |
| Tick marks | Outward on left and bottom only; right side tick-free |

---

## Design: Golden Ratio Throughout

| Element | Rule |
|---------|------|
| Figure aspect ratio | `height = width × 0.618` (golden rectangle) |
| Bar spacing — two-level hierarchy | boundary→bar edge : inner gap : bar width = `φ/2 : 1/φ : 1` ≈ `0.809 : 0.618 : 1`; all boundaries (spines and separators) are equidistant from their nearest bar |
| Inter-group gap (edge to edge) | `φ × bar_width ≈ 1.618` — gives total outer gap : inner gap = `φ² : 1` |
| Y-axis top padding | `0.618 × one tick interval` above the highest tick |
| Color darkening | Geometric series with ratio `0.618`; lightness steps are denser at the dark end |
| Legend internals | swatch side = `fs × 1.0`; swatch→text gap = `fs × 0.618`; row height = `fs × 1.618` |

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
│       ├── colors.py           # φ-geometric HSL palette generator
│       └── ticks.py            # nice_ticks() / nice_range()
├── examples/
│   └── ablation_example.csv    # Sample input
├── main.py                     # CLI entry point (argparse)
├── requirements.txt
└── README.md
```

### Extending with a New Chart Mode

1. Create `golden_ratio_plot/renderer/<mode>.py` with a class that inherits from `BaseRenderer`.
2. Implement `_draw(self, fig, ax, data)` — the base class handles style, spines, ticks, and saving.
3. Add the new mode name to `_MODES` in `main.py` and add the corresponding `elif` dispatch branch.
