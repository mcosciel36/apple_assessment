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

_RE_PRECIP_IN = re.compile(r"(?i)precip\s*\(in\)\s*([0-9.]+%?)")
_RE_PRECIP_SPACE_IN = re.compile(r"(?i)precip\s+([0-9.]+%?)\s*in\b")
_RE_PRECIP_TOKEN = re.compile(r"(?i)precip\s+(?!ation)([0-9.]+%?)(?=\s+Precip|\s+CDD|\s*[*]|\s*$)")
_RE_DAILY_LEADING = re.compile(r"(?i)^\s*DAILY\s+(-?\d+(?:\.\d+)?)")
_RE_MAX_TABLE_LINE = re.compile(r"(?i)^\s*Max\s*\(°?\s*F\)\s+(-?\d+(?:\.\d+)?)")
_RE_MIN_TABLE_LINE = re.compile(r"(?i)^\s*Min\s*\(°?\s*F\)\s+(-?\d+(?:\.\d+)?)")
_RE_MAX_DEG = re.compile(r"(?i)^\s*Max\s+(-?\d+(?:\.\d+)?)\s*°?\s*F")
_RE_MIN_DEG = re.compile(r"(?i)^\s*Min\s+(-?\d+(?:\.\d+)?)\s*°?\s*F")
_RE_DAILY_AVG = re.compile(
    r"(?i)DAILY\s+Avg\s+Temp(?:\s*\(°?\s*F\)?)?\s+(-?\d+(?:\.\d+)?)"
)
_RE_AVG_LINE = re.compile(
    r"(?i)^\s*Avg\s*(?:\(°?\s*F\))?\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?"
)
_RE_PRECIPITATION_ROW = re.compile(r"(?i)^\s*Precipitation\s+([0-9.]+%?)")


def _all_daily_observations_missing(full_text: str) -> bool:
    """True when the PDF states observed daily metrics are *M* (e.g. March 18 layout)."""
    if re.search(r"(?i)all daily observations\s+MISSING", full_text):
        return True
    if re.search(r"(?i)daily observations\s+MISSING\s*\(M\)", full_text):
        return True
    return False


def parse_pdf_observation(pdf_path: Path) -> ParsedObservation | None:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)

    obs_date = _extract_date(full_text)
    if obs_date is None:
        return None

    if _all_daily_observations_missing(full_text):
        return ParsedObservation(
            observation_date=obs_date,
            temp_max_f=None,
            temp_min_f=None,
            temp_avg_f=None,
            temp_departure=None,
            hdd=None,
            cdd=None,
            precip_inches=None,
            snow_depth=None,
            quality_flag="missing_marked",
            parse_notes="daily observations marked missing (M) in source PDF",
            raw_excerpt="\n".join(full_text.splitlines()[:40]),
        )

    observation = ParsedObservation(
        observation_date=obs_date,
        temp_max_f=_extract_max_temp_f(full_text),
        temp_min_f=_extract_min_temp_f(full_text),
        temp_avg_f=_extract_avg_temp_f(full_text),
        precip_inches=_extract_precip_inches(full_text),
        hdd=_extract_metric(full_text, ["Heating Degree Days", "HDD"]),
        cdd=_extract_metric(full_text, ["Cooling Degree Days", "CDD"]),
        snow_depth=_extract_metric(full_text, ["Snow Depth"]),
        raw_excerpt="\n".join(full_text.splitlines()[:40]),
    )

    if "QC FLAG: 0" in full_text:
        observation.quality_flag = "qc_0"

    return observation


def _extract_precip_inches(full_text: str) -> float | None:
    """Structured precip — avoids ``precip`` matching inside ``precipitation`` prose (Mar 14)."""
    for line in full_text.splitlines():
        m = _RE_PRECIP_IN.search(line)
        if m:
            v = parse_numeric(m.group(1))
            if v is not None:
                return v
    for line in full_text.splitlines():
        m = _RE_PRECIP_SPACE_IN.search(line)
        if m:
            v = parse_numeric(m.group(1))
            if v is not None:
                return v
    for line in full_text.splitlines():
        m = _RE_PRECIPITATION_ROW.match(line.strip())
        if m:
            v = parse_numeric(m.group(1))
            if v is not None:
                return v
    for line in full_text.splitlines():
        m = _RE_PRECIP_TOKEN.search(line)
        if m:
            v = parse_numeric(m.group(1))
            if v is not None:
                return v
    if re.search(r"(?i)\bno\s+precipitation\b", full_text):
        return 0.0
    return None


def _skip_line_for_daily_max(line: str) -> bool:
    s = line.strip()
    if re.match(r"(?i)MTD\b", s):
        return True
    if re.match(r"(?i)Avg\s+Max\b", s):
        return True
    return False


def _skip_line_for_daily_min(line: str) -> bool:
    s = line.strip()
    if re.match(r"(?i)MTD\b", s):
        return True
    if re.match(r"(?i)Avg\s+Min\b", s):
        return True
    return False


def _first_daily_after_header(full_text: str, header_pattern: str) -> float | None:
    lines = full_text.splitlines()
    for i, line in enumerate(lines):
        if re.search(header_pattern, line, re.I):
            for j in range(i + 1, min(i + 8, len(lines))):
                m = _RE_DAILY_LEADING.match(lines[j])
                if m:
                    return parse_numeric(m.group(1))
    return None


def _extract_max_temp_f(full_text: str) -> float | None:
    for line in full_text.splitlines():
        if _skip_line_for_daily_max(line):
            continue
        m = _RE_MAX_TABLE_LINE.match(line)
        if m:
            return parse_numeric(m.group(1))
        m = _RE_MAX_DEG.match(line)
        if m:
            return parse_numeric(m.group(1))
    v = _first_daily_after_header(full_text, r"Max\s+Temp")
    if v is not None:
        return v
    return _extract_metric(full_text, ["Max Temperature", "Max Temp"])


def _extract_min_temp_f(full_text: str) -> float | None:
    for line in full_text.splitlines():
        if _skip_line_for_daily_min(line):
            continue
        m = _RE_MIN_TABLE_LINE.match(line)
        if m:
            return parse_numeric(m.group(1))
        m = _RE_MIN_DEG.match(line)
        if m:
            return parse_numeric(m.group(1))
    v = _first_daily_after_header(full_text, r"Min\s+Temp")
    if v is not None:
        return v
    return _extract_metric(full_text, ["Min Temperature", "Min Temp"])


def _bad_avg_line(line: str) -> bool:
    s = line.strip()
    if re.match(r"(?i)MTD\b", s):
        return True
    # Skip MTD-style rows that *start* with Avg Max / Avg Min, not ``Avg 73°F Avg Min …``.
    if re.match(r"(?i)Avg\s+Max\b", s):
        return True
    if re.match(r"(?i)Avg\s+Min\b", s):
        return True
    return False


def _extract_avg_temp_f(full_text: str) -> float | None:
    for line in full_text.splitlines():
        m = _RE_DAILY_AVG.search(line)
        if m:
            return parse_numeric(m.group(1))
    for line in full_text.splitlines():
        if _bad_avg_line(line):
            continue
        m = _RE_AVG_LINE.match(line)
        if m:
            return parse_numeric(m.group(1))
    return _extract_metric(
        full_text,
        ["Avg Temperature", "Avg Temp", "Avg Temperature (°F)"],
    )


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
    """Take the first numeric token *after* the matched label on that line."""
    lines = full_text.splitlines()
    for line in lines:
        lower_line = line.lower()
        for label in labels:
            lower_label = label.lower()
            idx = lower_line.find(lower_label)
            if idx == -1:
                continue
            # Skip ``YTD HDD`` / ``YTD CDD`` on the same physical line as other metrics (Mar 9).
            if "ytd" in lower_line[:idx]:
                continue
            suffix = line[idx + len(label) :]
            tokens = re.findall(r"-?\d+(?:\.\d+)?%?", suffix)
            if not tokens:
                continue
            parsed = parse_numeric(tokens[0])
            if parsed is not None:
                return parsed
    return None
