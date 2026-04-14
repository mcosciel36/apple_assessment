from __future__ import annotations

import csv
import re
from pathlib import Path

from weather_project.parsers.common import ParsedObservation, parse_mmddyy, parse_numeric


MONTH_HEADER_PAT = re.compile(r"^\d{2}-[A-Za-z]{3}$")
DATA_DATE_PAT = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
SKIP_PREFIXES = ("Sum", "Average", "Normal", "Above Normals")


def parse_csv_observations(csv_path: Path) -> list[ParsedObservation]:
    rows: list[list[str]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = [row for row in reader]

    if not rows:
        return []

    observations: list[ParsedObservation] = []
    max_cols = max(len(row) for row in rows)

    for col in range(max_cols):
        for row in rows:
            if col >= len(row):
                continue
            cell = row[col].strip()
            if not DATA_DATE_PAT.match(cell):
                continue
            if any(cell.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue

            parsed_date = parse_mmddyy(cell)
            if parsed_date is None:
                continue

            fields = _safe_slice(row, col, 9)
            notes: list[str] = []
            quality_flag: str | None = None

            if len(fields) < 8:
                notes.append("short_row")

            if "NO WEATHER" in ",".join(fields):
                quality_flag = "missing_no_weather"
            if any(token == "M" for token in fields):
                quality_flag = "missing_marked"
            if any(token == "ERROR" for token in fields):
                quality_flag = "parse_error_token"

            observation = ParsedObservation(
                observation_date=parsed_date,
                temp_max_f=parse_numeric(_field(fields, 1)),
                temp_min_f=parse_numeric(_field(fields, 2)),
                temp_avg_f=parse_numeric(_field(fields, 3)),
                temp_departure=parse_numeric(_field(fields, 4)),
                hdd=parse_numeric(_field(fields, 5)),
                cdd=parse_numeric(_field(fields, 6)),
                precip_inches=parse_numeric(_field(fields, 7)),
                quality_flag=quality_flag,
                parse_notes=";".join(notes) if notes else None,
                raw_excerpt=",".join(fields),
            )
            observations.append(observation)

    deduped: dict[str, ParsedObservation] = {}
    for item in observations:
        key = item.observation_date.isoformat()
        # Prefer the row with a real max temp over malformed duplicates.
        existing = deduped.get(key)
        if existing is None or (
            existing.temp_max_f is None and item.temp_max_f is not None
        ):
            deduped[key] = item
    return sorted(deduped.values(), key=lambda x: x.observation_date)


def _safe_slice(row: list[str], col: int, width: int) -> list[str]:
    values: list[str] = []
    for i in range(col, col + width):
        values.append(row[i].strip() if i < len(row) else "")
    return values


def _field(fields: list[str], idx: int) -> str:
    return fields[idx] if idx < len(fields) else ""
