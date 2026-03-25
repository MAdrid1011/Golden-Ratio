from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


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

        for i, row in enumerate(reader, start=2):
            group = row["group"].strip()
            label = row["label"].strip()
            raw_value = row[value_col].strip()

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
