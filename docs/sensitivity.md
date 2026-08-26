# Sensitivity Study Charts

Sensitivity mode generates a horizontal grid of dual-axis line charts, one panel per CSV file.  Each panel has a **red left y-axis** and a **blue right y-axis** sharing the same set of aligned tick levels, connected by gray dashed gridlines.  All spines and tick marks are black; only the axis labels and tick numbers carry color.

---

## Quick Examples

```bash
# Two-panel sensitivity study (side by side)
python main.py --mode sensitivity \
  --inputs examples/demo_sensitivity_lr.csv \
           examples/demo_sensitivity_depth.csv \
  --output out/Sensitivity_demo --font_size_pt 6

# Three-panel study
python main.py --mode sensitivity \
  --inputs examples/sensitivity_K.csv \
           examples/sensitivity_lambda.csv \
           examples/sensitivity_alpha.csv \
  --output out/Sensitivity

# Single panel (same mode, one CSV)
python main.py --mode sensitivity \
  --input examples/sensitivity_K.csv \
  --output out/Sensitivity_K
```

Each run produces both a `.pdf` and a `.png` at the output path.

---

## CSV Format

Four columns are required.  Column names are arbitrary — the third column header becomes the **left y-axis label** and the fourth becomes the **right y-axis label**.

```csv
group,x,Left Label,Right Label
__caption__,,(a) Panel Title,
Method A,1,82.3,24.5
Method A,2,85.1,23.2
Method A,4,87.0,22.0
Method A,8,86.0,18.5
```

| Column | Role |
|--------|------|
| `group` | Series / method name. Leave **blank** for a single unnamed series (no legend rendered). |
| `x` | X-axis parameter value; displayed as a category tick label (evenly spaced). |
| *(col 3)* | Left y-axis values. Column header → left axis label. |
| *(col 4)* | Right y-axis values. Column header → right axis label. |

**Rules**
- Every `(group, x)` pair must be unique.
- Every group must supply a value for every x.

### Single-series example (no legend)

```csv
group,x,FPS,PSNR (dB)
__caption__,,(a) Effect of K,
,1,1281.3,32.74
,2,1274.9,32.86
,4,1262.3,32.87
,8,1240.1,32.88
```

### Multi-series example (legend shown)

```csv
group,x,Accuracy (%),FPS
__caption__,,(a) Effect of K,
Method A,1,81.2,28.4
Method A,2,84.7,25.1
Method A,4,87.3,21.6
Method A,8,86.5,17.8
Method B,1,78.5,30.2
Method B,2,82.1,27.0
Method B,4,85.0,23.4
Method B,8,84.2,19.1
```

---

## Metadata Rows

Metadata rows begin with a special `group` token and are stripped before rendering.

### `__xlabel__` — x-axis quantity name

```csv
__xlabel__,Active records per Pod,,
```

When a panel also has a caption, the quantity name is placed immediately above
the panel caption.

### `__caption__` — panel subtitle

```csv
__caption__,,(a) Effect of Learning Rate,
```

Rendered below the x-axis tick labels, 1 pt larger than the tick-label font.

### `__ymode__` — axis variation mode

Controls whether an axis "zooms in" on the data range or shows the full stable context.

```csv
__ymode__,,variation,stable
```

| Value | Behaviour |
|-------|-----------|
| `variation` *(default)* | Axis range tightly tracks the data span to maximise visual variation. |
| `stable` | Axis range is expanded to 10× the actual data span, so a nearly-flat line communicates stability rather than noise. |

The third column sets the mode for the **left axis**; the fourth column sets the **right axis**.

**Example** — FPS varies, PSNR is stable:

```csv
group,x,FPS,PSNR (dB)
__caption__,,(a) Coffee Martini,
__ymode__,,variation,stable
,15%,1259.2,32.85
,20%,1270.9,32.86
,25%,1279.4,32.86
,30%,1279.2,32.87
,35%,1278.5,32.86
```

### `__interp__` — smooth interpolation with jitter

Inserts *N* extra points between each consecutive pair of original data points using a Catmull-Rom spline, then adds smooth band-limited jitter.  The result looks like real scattered measurements connected by a trend line.

```csv
__interp__,,8,
```

The value is placed in the third column.  Set it to `0` or omit the row entirely to disable.

**Guarantees**
- The spline passes **exactly** through every original data point — the connecting line always runs through each circle/square marker.
- Jitter amplitude is ~1.8 % of the data span, smoothed to prevent white-noise appearance.
- Interpolated points are clamped strictly inside `(y_min, y_max)` of the original data — no interpolated point equals or exceeds the true extremes.

---

## Panel Layout

The total figure width is always `--width_pt` (default 240 pt).

| Panel count | Arrangement |
|-------------|-------------|
| 1 – 4 | One row of *n* panels, unless `--panel_cols` requests an even grid |
| *n* > 4 and *n* divisible by 3 | Rows of 3 (preferred) |
| *n* > 4 and *n* divisible by 2 | Rows of 2 |
| otherwise | **Error** — choose a panel count that satisfies one of the above |

Each panel cell has aspect ratio φ : 1 (width : height, φ ≈ 1.618).

---

## Axis Conventions

| Axis | Color | Notes |
|------|-------|-------|
| Left y-axis | Red (`#EE3311`) | Tick labels + axis title colored; spine and tick marks black |
| Right y-axis | Blue (`#0099DD`) | Tick labels + axis title colored; spine and tick marks black |
| X-axis | Black | Tick labels shown; no axis title |
| Top spine | Black | Visible (all four sides closed) |

Both y-axes always have **6 ticks** at identical fractional heights, so horizontal gray dashed gridlines align exactly with both axis tick levels.  Y-ranges are chosen to maximise visual variation unless `__ymode__` is set to `stable`.

---

## Legend

A legend is rendered **only** when a panel contains more than one group.  Each entry pairs a color-coded line style with the group name.  Multiple groups are distinguished by line style (solid, dashed, dotted).  Data point markers are solid squares.

```
■ ────── ■   Method A      (solid)
■ - - -  ■   Method B      (dashed)
■ ······ ■   Method C      (dotted)
```

For single-group panels (blank `group` column) no legend is rendered.

---

## CLI Options (Sensitivity)

| Flag | Default | Description |
|------|---------|-------------|
| `--mode sensitivity` | — | **Required** to activate sensitivity mode. |
| `--inputs CSV …` | — | One CSV per panel, left-to-right (top-to-bottom for multi-row grids). |
| `--input CSV` | — | Shorthand for a single panel. |
| `--output PATH` | `out/figure` | Output base path (no extension). |
| `--formats fmt …` | `pdf png` | Output formats: `pdf`, `png`, `svg`, `eps`. |
| `--width_pt` | `240` | Total figure width in typographic points. |
| `--font_size_pt` | `7` | Font size in pt. **Sensitivity mode allows 6 pt** (ACM allows reduced size for sub-figures). |
| `--panel_cols` | `1` | Set to `2` to arrange four panels as a 2×2 grid. |

---

## Marker Style

Original data points are drawn as **solid squares**.  When `__interp__` is active, the dense interpolated points are drawn as **hollow squares** (outline only) of slightly smaller size.  The solid squares always render on top so the true data positions are unambiguous.

---

## Full Working Example

```bash
# 1. Create two CSV files:
#    demo_sensitivity_lr.csv   — Effect of Learning Rate
#    demo_sensitivity_depth.csv — Effect of Network Depth

# 2. Generate the two-panel figure at 6 pt font
python main.py --mode sensitivity \
  --inputs examples/demo_sensitivity_lr.csv \
           examples/demo_sensitivity_depth.csv \
  --output out/Sensitivity_demo \
  --font_size_pt 6
# → out/Sensitivity_demo.pdf
# → out/Sensitivity_demo.png
```

`demo_sensitivity_lr.csv`:

```csv
group,x,Accuracy (%),Latency (ms)
__caption__,,(a) Effect of Learning Rate,
__interp__,,8,
,1e-4,83.2,14.7
,3e-4,86.5,14.2
,1e-3,87.8,13.9
,3e-3,85.1,13.6
,1e-2,80.4,13.1
```

`demo_sensitivity_depth.csv`:

```csv
group,x,Accuracy (%),Latency (ms)
__caption__,,(b) Effect of Network Depth,
__interp__,,8,
,2,81.3,8.4
,4,84.9,11.2
,6,87.8,13.9
,8,87.2,17.6
,10,86.5,22.3
```
