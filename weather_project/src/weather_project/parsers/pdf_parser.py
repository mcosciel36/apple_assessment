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
_RE_NUMERIC_WITH_OPTIONAL_YEAR = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:°?\s*F|in(?:ches)?|in)?\s*(?:\((\d{4})\))?",
    re.IGNORECASE,
)

_METRIC_ALIASES = {
    "max temperature": "temp_max",
    "max temp": "temp_max",
    "max": "temp_max",
    "min temperature": "temp_min",
    "min temp": "temp_min",
    "min": "temp_min",
    "avg temperature": "temp_avg",
    "avg temp": "temp_avg",
    "avg": "temp_avg",
    "avg max": "avg_max_f",
    "avg min": "avg_min_f",
    "precipitation": "precip_inches",
    "precip": "precip_inches",
    "hdd": "hdd",
    "heating degree days": "hdd",
    "cdd": "cdd",
    "cooling degree days": "cdd",
    "snow depth": "snow_depth",
}


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

    full_values = _extract_full_values(full_text)

    observation = ParsedObservation(
        observation_date=obs_date,
        temp_max_f=_pick(
            full_values.get("daily_temp_max_obs"), _extract_max_temp_f(full_text)
        ),
        temp_min_f=_pick(
            full_values.get("daily_temp_min_obs"), _extract_min_temp_f(full_text)
        ),
        temp_avg_f=_pick(
            full_values.get("daily_temp_avg_obs"), _extract_avg_temp_f(full_text)
        ),
        precip_inches=_pick(
            full_values.get("daily_precip_inches_obs"), _extract_precip_inches(full_text)
        ),
        hdd=_pick(
            full_values.get("daily_hdd_obs"),
            _extract_metric(full_text, ["Heating Degree Days", "HDD"]),
        ),
        cdd=_pick(
            full_values.get("daily_cdd_obs"),
            _extract_metric(full_text, ["Cooling Degree Days", "CDD"]),
        ),
        snow_depth=_pick(
            full_values.get("daily_snow_depth_obs"), _extract_metric(full_text, ["Snow Depth"])
        ),
        raw_excerpt="\n".join(full_text.splitlines()[:40]),
        full_values=full_values,
    )

    if _all_daily_observations_missing(full_text):
        observation.quality_flag = "missing_marked"
        observation.parse_notes = "daily observations marked missing (M) in source PDF"
        observation.temp_max_f = None
        observation.temp_min_f = None
        observation.temp_avg_f = None
        observation.precip_inches = None
        observation.hdd = None
        observation.cdd = None
        observation.snow_depth = None

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


def _pick(primary: float | None, fallback: float | None) -> float | None:
    return primary if primary is not None else fallback


def _join_ytd_statistics_continuations(text: str) -> str:
    """Join ``YTD Statistics: … HDD`` when HDD/CDD continue on the next line (e.g. March 18)."""
    return re.sub(
        r"(?is)(YTD Statistics:.*?HDD)\s*\n\s*(\d+)\s*,\s*CDD\s+(\d+)",
        r"\1 \2, CDD \3",
        text,
    )


def _fill_daily_norms_from_normal_expectations_prose(
    full_text: str, values: dict[str, float | int | None]
) -> None:
    """Fill daily max/min normals from narrative when the PDF has no Obs/Norm table (March 10)."""
    if values.get("daily_temp_max_norm") is not None or values.get("daily_temp_min_norm") is not None:
        return
    m = re.search(
        r"(?is)normal expectations.*?high of (-?\d+(?:\.\d+)?)\s*°?\s*F.*?low of (-?\d+(?:\.\d+)?)\s*°?\s*F",
        full_text,
    )
    if not m:
        return
    values["daily_temp_max_norm"] = parse_numeric(m.group(1))
    values["daily_temp_min_norm"] = parse_numeric(m.group(2))


def _extract_full_values(full_text: str) -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = {}
    full_text = _join_ytd_statistics_continuations(full_text)
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    section = "daily"
    record_only = False
    pending_metric: str | None = None

    for line in lines:
        lower = line.lower()
        has_obs_header = "observed" in lower or re.search(r"(?i)\bobs\b", lower) is not None
        has_norm_header = "normal" in lower or re.search(r"(?i)\bnorm\b", lower) is not None
        if _parse_compact_mar13_daily_style(line, values):
            continue
        if "record high" in lower and "record low" in lower and not has_obs_header:
            record_only = True
            continue
        if has_obs_header and has_norm_header:
            record_only = False
        if "month-to-date" in lower:
            section = "mtd"
            record_only = False
            pending_metric = None
            continue
        if "ytd statistics" in lower:
            _parse_ytd_statistics_line(line, values)
            continue
        if re.match(r"(?i)^mtd\s+obs\b", line):
            _parse_period_obs_norm_row(line, "mtd", "obs", values)
            continue
        if re.match(r"(?i)^mtd\s+norm\b", line):
            _parse_period_obs_norm_row(line, "mtd", "norm", values)
            continue
        if re.match(r"(?i)^ytd\s+obs\b", line):
            _parse_period_obs_norm_row(line, "ytd", "obs", values)
            continue
        if re.match(r"(?i)^ytd\s+norm\b", line):
            _parse_period_obs_norm_row(line, "ytd", "norm", values)
            continue
        if re.match(r"(?i)^mtd\b", line):
            section = "mtd"
        elif re.match(r"(?i)^daily\b", line):
            section = "daily"

        if _parse_compact_mar16_style(line, values):
            continue
        metric = _extract_metric_label(line)
        if metric and _line_has_numeric_value(line):
            if not _is_structured_metric_line(metric, line):
                continue
            _assign_metric_values(values, section, metric, line, record_only=record_only)
            pending_metric = None
            continue
        if metric:
            pending_metric = metric
            continue

        if pending_metric and re.match(r"(?i)^(daily|mtd|ytd)\b", line):
            inline_section = line.split()[0].lower()
            _assign_metric_values(
                values, inline_section, pending_metric, line, record_only=record_only
            )
            pending_metric = None

    _fill_daily_norms_from_normal_expectations_prose(full_text, values)
    return values


def _parse_compact_mar16_style(line: str, values: dict[str, float | int | None]) -> bool:
    compact = re.match(
        r"(?i)^(Min|Avg|Precip|CDD)\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?\s+"
        r"(Avg Max|Avg Min|Precip|CDD)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+"
        r"(Avg Max|Avg Min|Precip|CDD)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
        line,
    )
    if not compact:
        return False
    lead_metric = _normalize_metric_key(compact.group(1))
    if lead_metric:
        values[f"daily_{lead_metric}_obs"] = parse_numeric(compact.group(2))
    mtd_metric = _normalize_metric_key(compact.group(3))
    ytd_metric = _normalize_metric_key(compact.group(6))
    if mtd_metric:
        values[f"mtd_{mtd_metric}_obs"] = parse_numeric(compact.group(4))
        values[f"mtd_{mtd_metric}_norm"] = parse_numeric(compact.group(5))
    if ytd_metric:
        values[f"ytd_{ytd_metric}_obs"] = parse_numeric(compact.group(7))
        values[f"ytd_{ytd_metric}_norm"] = parse_numeric(compact.group(8))
    return True


def _parse_compact_mar13_daily_style(line: str, values: dict[str, float | int | None]) -> bool:
    """Handle compact daily lines where multiple metrics share one line (Mar 13-style)."""
    # Footer ``YTD Statistics: … Avg Temp …, Precip 6.72 in`` matches the ``avg_precip`` regex
    # but is year-to-date prose, not a daily compact row (e.g. March 18 all-``M`` layout).
    if re.search(r"(?i)\bytd statistics\b", line):
        return False
    max_min = re.search(
        r"(?i)max\s+temp(?:erature)?\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?"
        r".*?min\s+temp(?:erature)?\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?",
        line,
    )
    if max_min:
        values["daily_temp_max_obs"] = parse_numeric(max_min.group(1))
        values["daily_temp_min_obs"] = parse_numeric(max_min.group(2))
        return True

    avg_precip = re.search(
        r"(?i)avg\s+temp(?:erature)?\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?"
        r".*?precip(?:itation)?\s+(-?\d+(?:\.\d+)?)\s*(?:in)?\b",
        line,
    )
    if avg_precip:
        values["daily_temp_avg_obs"] = parse_numeric(avg_precip.group(1))
        values["daily_precip_inches_obs"] = parse_numeric(avg_precip.group(2))
        return True

    rec = re.search(
        r"(?i)record\s+high\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?\s*\((\d{4})\)"
        r".*?record\s+low\s+(-?\d+(?:\.\d+)?)\s*°?\s*F?\s*\((\d{4})\)",
        line,
    )
    if rec:
        values["daily_temp_max_record_high"] = parse_numeric(rec.group(1))
        values["daily_temp_max_record_high_year"] = int(rec.group(2))
        values["daily_temp_max_record_low"] = parse_numeric(rec.group(3))
        values["daily_temp_max_record_low_year"] = int(rec.group(4))
        return True

    return False


def _parse_period_obs_norm_row(
    line: str, period: str, value_type: str, values: dict[str, float | int | None]
) -> None:
    nums = _numeric_pairs(line)
    if len(nums) < 4:
        return
    metric_order = ["avg_max_f", "avg_min_f", "precip_inches", "cdd"]
    for idx, metric in enumerate(metric_order):
        values[f"{period}_{metric}_{value_type}"] = nums[idx][0]


def _parse_ytd_statistics_line(line: str, values: dict[str, float | int | None]) -> None:
    patterns = [
        (r"Avg Max\s+(-?\d+(?:\.\d+)?)", "ytd_avg_max_f_obs"),
        (r"Avg Min\s+(-?\d+(?:\.\d+)?)", "ytd_avg_min_f_obs"),
        (r"Avg Temp\s+(-?\d+(?:\.\d+)?)", "ytd_temp_avg_obs"),
        (r"Precip\s+(-?\d+(?:\.\d+)?)", "ytd_precip_inches_obs"),
        (r"HDD\s+(-?\d+(?:\.\d+)?)", "ytd_hdd_obs"),
        (r"CDD\s+(-?\d+(?:\.\d+)?)", "ytd_cdd_obs"),
    ]
    for pat, key in patterns:
        m = re.search(pat, line, flags=re.IGNORECASE)
        if m:
            values[key] = parse_numeric(m.group(1))


def _assign_metric_values(
    values: dict[str, float | int | None],
    section: str,
    metric: str,
    line: str,
    *,
    record_only: bool,
) -> None:
    pairs = _numeric_pairs(line)
    if not pairs:
        return
    base = f"{section}_{metric}"
    if record_only:
        values[f"{base}_record_high"] = pairs[0][0]
        if pairs[0][1] is not None:
            values[f"{base}_record_high_year"] = pairs[0][1]
        if len(pairs) > 1:
            values[f"{base}_record_low"] = pairs[1][0]
            if pairs[1][1] is not None:
                values[f"{base}_record_low_year"] = pairs[1][1]
        return
    if len(pairs) == 1 and re.search(r"(?i)\bM\b", line):
        values[f"{base}_norm"] = pairs[0][0]
        return
    values[f"{base}_obs"] = pairs[0][0]
    if len(pairs) > 1:
        values[f"{base}_norm"] = pairs[1][0]
    if len(pairs) > 2:
        values[f"{base}_record_high"] = pairs[2][0]
        if pairs[2][1] is not None:
            values[f"{base}_record_high_year"] = pairs[2][1]
    if len(pairs) > 3:
        values[f"{base}_record_low"] = pairs[3][0]
        if pairs[3][1] is not None:
            values[f"{base}_record_low_year"] = pairs[3][1]


def _line_has_numeric_value(line: str) -> bool:
    return re.search(r"-?\d+(?:\.\d+)?", line) is not None


def _is_structured_metric_line(metric: str, line: str) -> bool:
    """Skip narrative prose lines that happen to contain metric words + numbers."""
    normalized = re.sub(r"\s+", " ", line.strip().lower())
    section_prefixes = ("daily ", "mtd ", "ytd ")
    metric_tokens = {
        "temp_max": ("max temperature", "max temp", "max (°f)", "max"),
        "temp_min": ("min temperature", "min temp", "min (°f)", "min"),
        "temp_avg": ("avg temperature", "avg temp", "avg (°f)", "avg"),
        "precip_inches": ("precipitation", "precip (in)", "precip "),
        "hdd": ("heating degree days", "hdd"),
        "cdd": ("cooling degree days", "cdd"),
        "snow_depth": ("snow depth",),
        "avg_max_f": ("avg max",),
        "avg_min_f": ("avg min",),
    }
    tokens = metric_tokens.get(metric, ())
    # Most structured table rows begin with the metric token, optionally with DAILY/MTD/YTD prefix.
    for token in tokens:
        if normalized.startswith(token):
            return True
        for prefix in section_prefixes:
            if normalized.startswith(prefix + token):
                return True
    return False


def _numeric_pairs(line: str) -> list[tuple[float, int | None]]:
    pairs: list[tuple[float, int | None]] = []
    for match in _RE_NUMERIC_WITH_OPTIONAL_YEAR.finditer(line):
        val = parse_numeric(match.group(1))
        if val is None:
            continue
        year = int(match.group(2)) if match.group(2) else None
        pairs.append((val, year))
    return pairs


def _extract_metric_label(line: str) -> str | None:
    lowered = line.lower()
    for alias in sorted(_METRIC_ALIASES, key=len, reverse=True):
        if re.search(rf"(?i)\b{re.escape(alias)}\b", lowered):
            normalized = _normalize_metric_key(alias)
            if normalized:
                return normalized
    return None


def _normalize_metric_key(raw: str) -> str | None:
    return _METRIC_ALIASES.get(raw.lower().strip())
