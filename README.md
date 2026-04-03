# Golden Ratio Plot

A Python plotting tool that generates ACM-compliant charts from CSV data.
Three chart types are supported: **ablation study bar charts**, **sensitivity study line charts**, and **comparison + decomposition bar charts**.
All spatial proportions are derived from the golden ratio φ ≈ 1.618.

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
# Ablation — single panel
python main.py --input examples/ablation_example_single.csv --output out/fig

# Ablation — two stacked panels, each with a right-axis line overlay
python main.py --inputs panel_a.csv panel_b.csv \
               --input_lines line_a.csv line_b.csv --output out/fig_multi

# Decomp — 2-bar comparison with stacked decomposition (numeric labels always shown)
python main.py --mode decomp \
  --input examples/decomp_pipeline.csv \
  --output out/Decomp_pipeline

# Sensitivity — two panels side by side with interpolation
python main.py --mode sensitivity \
  --inputs examples/demo_sensitivity_lr.csv \
           examples/demo_sensitivity_depth.csv \
  --output out/Sensitivity_demo --font_size_pt 6

# Sensitivity — three panels
python main.py --mode sensitivity \
  --inputs examples/sensitivity_K.csv \
           examples/sensitivity_lambda.csv \
           examples/sensitivity_alpha.csv \
  --output out/Sensitivity
```

Each run writes a `.pdf` and `.png` at the output path.

---

## Documentation

| Topic | File |
|-------|------|
| Ablation bar charts — CSV format, CLI options, multi-panel, line overlay, palette | [docs/ablation.md](docs/ablation.md) |
| Decomp charts — grouped stacked bars, color system, separator rules | [docs/decomp.md](docs/decomp.md) |
| Sensitivity line charts — CSV format, `__ymode__`, `__interp__`, layout rules, axis conventions | [docs/sensitivity.md](docs/sensitivity.md) |

---

## Project Structure

```
Golden-Ratio/
├── golden_ratio_plot/
│   ├── config.py               # PlotConfig dataclass
│   ├── reader.py               # CSV → typed data models
│   ├── renderer/
│   │   ├── base.py             # ACM style, spines, ticks, save
│   │   ├── ablation.py         # Grouped bar chart renderer
│   │   ├── decomp.py           # Comparison + decomposition bar chart renderer
│   │   └── sensitivity.py      # Dual-axis line chart renderer
│   └── utils/
│       ├── colors.py           # Palette generation
│       ├── labels.py           # X-axis label wrapping helpers, AXES_WIDTH_FRACTION
│       ├── legend.py           # Legend row packing, stacking, finalization
│       └── ticks.py            # Nice tick / range utilities
├── examples/
│   ├── ablation_example_single.csv
│   ├── ablation_example_double.csv
│   ├── demo_sensitivity_lr.csv
│   ├── demo_sensitivity_depth.csv
│   └── decomp_pipeline.csv
├── docs/
│   ├── ablation.md
│   ├── decomp.md
│   └── sensitivity.md
├── main.py
└── requirements.txt
```
