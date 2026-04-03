from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class AblationData:
    """Structured data for an ablation-mode bar chart.

    Attributes
    ----------
    groups      : ordered list of group names (x-axis positions)
    labels      : ordered list of unique variant labels (legend entries)
    data        : dict mapping (group, label) → value
    value_label : the CSV column header for the numeric column — used
                  directly as the y-axis label (e.g. ``"Accuracy (%)"``).
    """
    groups: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    data: Dict[Tuple[str, str], float] = field(default_factory=dict)
    value_label: str = "value"
    caption: str = ""

    @property
    def n_groups(self) -> int:
        return len(self.groups)

    @property
    def n_labels(self) -> int:
        return len(self.labels)

    def get(self, group: str, label: str) -> float:
        """Return value for (group, label); raises KeyError if missing."""
        return self.data[(group, label)]

    def all_values(self) -> List[float]:
        return list(self.data.values())


def read_csv(path: str | Path) -> AblationData:
    """Read a CSV file into :class:`AblationData`.

    Required columns: ``group``, ``label``, and **exactly one other column**
    whose header becomes the y-axis label.  The header can include a unit,
    e.g. ``Accuracy (%)`` or ``Speedup (×)``.

    Raises
    ------
    ValueError
        If required columns are missing, more than one value column is found,
        or a cell cannot be parsed as float.
    FileNotFoundError
        If the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    groups_seen: list[str] = []
    labels_seen: list[str] = []
    data: Dict[Tuple[str, str], float] = {}

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        _validate_fieldnames(reader.fieldnames)
        value_col = _detect_value_column(reader.fieldnames)

        caption = ""
        for i, row in enumerate(reader, start=2):
            group = row["group"].strip()
            label = row["label"].strip()
            raw_value = row[value_col].strip()

            # Metadata rows: group starts with "__" (e.g. "__caption__")
            if group.startswith("__"):
                if group == "__caption__":
                    caption = raw_value
                continue

            if not group or not label:
                raise ValueError(f"Row {i}: 'group' and 'label' must not be empty.")
            try:
                value = float(raw_value)
            except ValueError:
                raise ValueError(
                    f"Row {i}: value column '{value_col}' must be a number, "
                    f"got {raw_value!r}."
                )

            if group not in groups_seen:
                groups_seen.append(group)
            if label not in labels_seen:
                labels_seen.append(label)

            key = (group, label)
            if key in data:
                raise ValueError(
                    f"Row {i}: duplicate (group, label) pair: {key}."
                )
            data[key] = value

    return AblationData(
        groups=groups_seen,
        labels=labels_seen,
        data=data,
        value_label=value_col,
        caption=caption,
    )


# ── Sensitivity study data model and reader ───────────────────────────────────

@dataclass
class SensitivityData:
    """Data for one sensitivity-study subplot (dual-axis line chart).

    Attributes
    ----------
    groups      : ordered unique group/method names; ``[""]`` = single unnamed group.
    x_values    : ordered x-axis category labels (strings, shown on x-axis ticks).
    left_label  : left y-axis label — taken from the CSV column header.
    right_label : right y-axis label — taken from the CSV column header.
    left_data   : group → list of left-y values, aligned with ``x_values``.
    right_data  : group → list of right-y values, aligned with ``x_values``.
    caption     : subfigure label, e.g. ``"(a) Effect of K"``.
    """

    groups: List[str] = field(default_factory=list)
    x_values: List[str] = field(default_factory=list)
    left_label: str = "Left"
    right_label: str = "Right"
    left_data: Dict[str, List[float]] = field(default_factory=dict)
    right_data: Dict[str, List[float]] = field(default_factory=dict)
    caption: str = ""
    left_mode: str = "variation"   # "variation" | "stable"
    right_mode: str = "variation"  # "variation" | "stable"
    interp_pts: int = 0            # extra points between each pair (0 = off)

    @property
    def n_groups(self) -> int:
        return len(self.groups)

    @property
    def all_left_values(self) -> List[float]:
        return [v for vs in self.left_data.values() for v in vs]

    @property
    def all_right_values(self) -> List[float]:
        return [v for vs in self.right_data.values() for v in vs]


def read_sensitivity_csv(path: str | Path) -> SensitivityData:
    """Read a sensitivity-study CSV into :class:`SensitivityData`.

    CSV format — four columns in order:

    .. code-block:: text

        group, x, <Left Axis Label>, <Right Axis Label>

    - ``group`` : method / series name.  Leave blank for a single unnamed group.
    - ``x``     : x-axis parameter value, treated as a category label.
    - Two value columns whose **headers** become the left and right y-axis labels.
    - A row with ``group = __caption__`` stores the subfigure caption text in
      the first value column (the right value column is ignored for that row).

    Single-group example::

        group,x,Accuracy (%),FPS
        __caption__,,(a) Effect of K,
        ,1,82.3,24.5
        ,2,85.1,23.2
        ,4,87.0,22.0

    Multi-group example::

        group,x,Accuracy (%),FPS
        __caption__,,(a) Effect of K,
        Method A,1,82.3,24.5
        Method A,2,85.1,23.2
        Method B,1,78.0,26.0
        Method B,2,80.5,24.8

    Raises
    ------
    FileNotFoundError
        If the CSV path does not exist.
    ValueError
        If required columns are missing, value columns ≠ 2, or non-numeric data.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames: List[str] = list(reader.fieldnames or [])

        # Validate required columns
        lower = [f.strip().lower() for f in fieldnames]
        if "group" not in lower:
            raise ValueError("Sensitivity CSV must have a 'group' column.")
        if "x" not in lower:
            raise ValueError("Sensitivity CSV must have an 'x' column.")
        reserved = {"group", "x"}
        value_cols = [f for f in fieldnames if f.strip().lower() not in reserved]
        if len(value_cols) != 2:
            raise ValueError(
                f"Sensitivity CSV must have exactly 2 value columns (left and right); "
                f"found {len(value_cols)}: {value_cols}."
            )
        left_col, right_col = value_cols

        # Collect raw rows first so we can align all groups to the same x_values
        rows: List[Tuple[str, str, float, float]] = []
        caption = ""
        left_mode = "variation"
        right_mode = "variation"
        interp_pts = 0

        for i, row in enumerate(reader, start=2):
            group = row["group"].strip()
            x_raw = row["x"].strip()
            left_raw = (row[left_col] or "").strip()
            right_raw = (row[right_col] or "").strip()

            if group.startswith("__"):
                if group == "__caption__":
                    caption = left_raw or right_raw
                elif group == "__ymode__":
                    if left_raw:
                        left_mode = left_raw.lower()
                    if right_raw:
                        right_mode = right_raw.lower()
                elif group == "__interp__":
                    try:
                        interp_pts = int(left_raw or right_raw)
                    except ValueError:
                        pass
                continue

            try:
                lv = float(left_raw)
            except ValueError:
                raise ValueError(
                    f"Row {i}: left value '{left_raw}' in column '{left_col}' is not a number."
                )
            try:
                rv = float(right_raw)
            except ValueError:
                raise ValueError(
                    f"Row {i}: right value '{right_raw}' in column '{right_col}' is not a number."
                )

            rows.append((group, x_raw, lv, rv))

    if not rows:
        raise ValueError(f"Sensitivity CSV has no data rows: {path}")

    # Build ordered groups and x_values (preserve first-seen order)
    groups_seen: List[str] = list(dict.fromkeys(g for g, _, _, _ in rows))
    x_seen: List[str] = list(dict.fromkeys(x for _, x, _, _ in rows))

    # Index data by (group, x) for alignment
    data_map: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for group, x_raw, lv, rv in rows:
        key = (group, x_raw)
        if key in data_map:
            raise ValueError(
                f"Duplicate (group='{group}', x='{x_raw}') in sensitivity CSV."
            )
        data_map[key] = (lv, rv)

    left_data: Dict[str, List[float]] = {}
    right_data: Dict[str, List[float]] = {}
    for g in groups_seen:
        left_data[g] = []
        right_data[g] = []
        for x in x_seen:
            if (g, x) not in data_map:
                raise ValueError(
                    f"Group '{g}' has no value for x='{x}'."
                )
            lv, rv = data_map[(g, x)]
            left_data[g].append(lv)
            right_data[g].append(rv)

    return SensitivityData(
        groups=groups_seen,
        x_values=x_seen,
        left_label=left_col,
        right_label=right_col,
        left_data=left_data,
        right_data=right_data,
        caption=caption,
        left_mode=left_mode,
        right_mode=right_mode,
        interp_pts=interp_pts,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_fieldnames(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("CSV file appears to be empty.")
    lower = {f.strip().lower() for f in fieldnames}
    for required in ("group", "label"):
        if required not in lower:
            raise ValueError(
                f"CSV is missing required column '{required}'. "
                f"Found: {', '.join(fieldnames)}."
            )


def _detect_value_column(fieldnames: list[str]) -> str:
    """Return the one column that is neither 'group' nor 'label'.

    The column name is used verbatim as the y-axis label, so you can write
    the unit directly in the header, e.g. ``Accuracy (%)`` or ``Speedup (×)``.
    """
    reserved = {"group", "label"}
    value_cols = [f for f in fieldnames if f.strip().lower() not in reserved]
    if not value_cols:
        raise ValueError(
            "CSV must contain a value column (any column other than "
            "'group' and 'label')."
        )
    if len(value_cols) > 1:
        raise ValueError(
            f"CSV has multiple value columns: {value_cols}. "
            "Only one value column is supported per chart."
        )
    return value_cols[0]
