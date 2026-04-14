from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from weather_project.parsers.common import ParsedObservation, parse_numeric


DATE_TEXT_PATTERNS = [
    re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})"),
    re.compile(r"([A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})", re.IGNORECASE),
    re.compile(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", re.IGNORECASE),
]


def parse_pdf_observation(pdf_path: Path) -> ParsedObservation | None:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)

    obs_date = _extract_date(full_text)
    if obs_date is None:
        return None

    observation = ParsedObservation(
        observation_date=obs_date,
        temp_max_f=_extract_metric(full_text, ["Max Temperature", "Max Temp", "Max"]),
        temp_min_f=_extract_metric(full_text, ["Min Temperature", "Min Temp", "Min"]),
        temp_avg_f=_extract_metric(
            full_text, ["Avg Temperature", "Avg Temp", "Avg Temperature (°F)", "Avg"]
        ),
        precip_inches=_extract_metric(full_text, ["Precipitation", "Precip"]),
        hdd=_extract_metric(full_text, ["Heating Degree Days", "HDD"]),
        cdd=_extract_metric(full_text, ["Cooling Degree Days", "CDD"]),
        snow_depth=_extract_metric(full_text, ["Snow Depth"]),
        raw_excerpt="\n".join(full_text.splitlines()[:40]),
    )

    if "MISSING" in full_text or "Missing (M)" in full_text:
        observation.quality_flag = "missing_marked"
        observation.parse_notes = "daily observations missing in source PDF"
    elif "QC FLAG: 0" in full_text:
        observation.quality_flag = "qc_0"

    return observation


def _extract_date(full_text: str):
    for pattern in DATE_TEXT_PATTERNS:
        match = pattern.search(full_text)
        if not match:
            continue
        parsed = _parse_date_token(match.group(1))
        if parsed is not None:
            return parsed
    return None


def _parse_date_token(token: str):
    from weather_project.parsers.common import extract_date_from_text, parse_mmddyy

    cleaned = token.strip()
    parsed = parse_mmddyy(cleaned)
    if parsed is not None:
        return parsed

    cleaned = re.sub(r"(\d)(st|nd|rd|th)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(".", "")
    parsed = extract_date_from_text(cleaned)
    if parsed is not None:
        return parsed

    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _extract_metric(full_text: str, labels: list[str]) -> float | None:
    lines = full_text.splitlines()
    for line in lines:
        for label in labels:
            if label not in line:
                continue
            tokens = re.findall(r"-?\d+(?:\.\d+)?%?", line)
            if not tokens:
                continue
            parsed = parse_numeric(tokens[0])
            if parsed is not None:
                return parsed
    return None
