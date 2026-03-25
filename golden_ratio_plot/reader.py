from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class BarEntry:
    """A single bar: which group it belongs to, its label, and its numeric value."""
    group: str
    label: str
    value: float


@dataclass
class AblationData:
    """Structured data for an ablation-mode bar chart.

    Attributes
    ----------
    groups : ordered list of group names (x-axis positions)
    labels : ordered list of unique variant labels (legend entries, consistent across groups)
    data   : dict mapping (group, label) → value
    """
    groups: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    data: Dict[Tuple[str, str], float] = field(default_factory=dict)

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

    Expected columns (in any order): ``group``, ``label``, ``value``.

    Raises
    ------
    ValueError
        If required columns are missing or a value cannot be parsed as float.
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
        _validate_fieldnames(reader.fieldnames, {"group", "label", "value"})

        for i, row in enumerate(reader, start=2):
            group = row["group"].strip()
            label = row["label"].strip()
            raw_value = row["value"].strip()

            if not group or not label:
                raise ValueError(f"Row {i}: 'group' and 'label' must not be empty.")
            try:
                value = float(raw_value)
            except ValueError:
                raise ValueError(
                    f"Row {i}: 'value' must be a number, got {raw_value!r}."
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

    return AblationData(groups=groups_seen, labels=labels_seen, data=data)


def _validate_fieldnames(
    fieldnames: list[str] | None,
    required: set[str],
) -> None:
    if fieldnames is None:
        raise ValueError("CSV file appears to be empty.")
    actual = {f.strip().lower() for f in fieldnames}
    missing = required - actual
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(sorted(missing))}. "
            f"Found: {', '.join(sorted(fieldnames))}."
        )
