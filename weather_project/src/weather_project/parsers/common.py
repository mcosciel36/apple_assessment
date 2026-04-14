from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime


DATE_PAT = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")


@dataclass
class ParsedObservation:
    observation_date: date
    temp_max_f: float | None = None
    temp_min_f: float | None = None
    temp_avg_f: float | None = None
    temp_departure: float | None = None
    hdd: float | None = None
    cdd: float | None = None
    precip_inches: float | None = None
    snow_depth: float | None = None
    quality_flag: str | None = None
    parse_notes: str | None = None
    raw_excerpt: str | None = None


def parse_mmddyy(value: str) -> date | None:
    match = DATE_PAT.search(value.strip())
    if not match:
        return None
    month, day, year = match.groups()
    year_int = int(year)
    if year_int < 100:
        year_int += 2000
    return date(year_int, int(month), int(day))


def parse_numeric(value: str) -> float | None:
    cleaned = value.strip()
    if cleaned in {"", "-", "—", "M", "ERROR", "NO WEATHER"}:
        return None
    cleaned = cleaned.replace("%", "")
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_date_from_text(text: str) -> date | None:
    maybe = parse_mmddyy(text)
    if maybe:
        return maybe

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y"):
        try:
            cleaned = re.sub(r"\s+", " ", text).strip()
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None
