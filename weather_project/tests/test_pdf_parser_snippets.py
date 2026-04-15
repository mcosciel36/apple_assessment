"""Regression snippets for PDF metric extraction (layout edge cases)."""

from pathlib import Path

import pytest

from weather_project.parsers import pdf_parser as pp


MAR14_SNIPPET = """
MARCH 14, 2026 — LOS ANGELES DOWNTOWN, CA
No precipitation was recorded. Record data for this date: High of 93°F (2015), Low of
50°F (2025).
DAILY Observed Normal Rec High Rec Low
Max (°F) 83 70 93 (2015) 50 (2025)
Min (°F) 56 52 62 (2015) 39 (1895)
Avg (°F) 69.5 61.0 — —
Precip (in) 0.00 0.08 — —
""".strip()


MAR16_SNIPPET = """
MARCH 16, 2026 — LOS ANGELES DOWNTOWN, CA
DAILY Value
Max 90°F MTD Obs Norm YTD Obs Norm
Min 56°F Avg Max 79.7 69.3 Avg Max 75.3 68.3
Avg 73.0°F Avg Min 54.4 51.8 Avg Min 51.2 49.9
Precip 0.00 Precip 0.00 1.40 Precip 6.72 8.33
CDD 8 CDD 52 11 CDD 138 30
""".strip()


MAR10_PROSE_NORMS = """
WEATHER REPORT MARCH 10, 2026
On March 10th, 2026, Los Angeles experienced moderate temperatures with a high of 70°F and a low of 55°F, averaging
62.5°F throughout the day. Normal expectations for this date call for a high of 69°F and low of 52°F, suggesting
slightly warmer conditions.
DAILY OBSERVATIONS Value
Max Temperature 70°F
Min Temperature 55°F
""".strip()


MAR17_SNIPPET = """
MARCH 17, 2026 — LOS ANGELES DOWNTOWN, CA
Section Metric Obs Norm Record High Record Low
Max Temp
DAILY 98 70 98 (2026) 47 (1945)
(°F)
Min Temp
DAILY 64 53 66 (1978) 37 (1881)
DAILY Avg Temp (°F) 81.0 61.3 — —
MTD Avg Max (°F) 80.8 69.3 80.8 (2026) 58.3 (1952)
""".strip()


MAR13_COMBINED_LINE = """
WEATHER DATA — 13-MAR-2026
Max Temp 92°F Min Temp 62°F
Avg Temp 77.0°F Precip 0.00 in
""".strip()

MAR13_RECORD_COMBINED_LINE = """
Record High 92°F (2026) Record Low 52°F (1895) YTD AvgMax: 74.9
""".strip()


def test_mar14_precip_not_from_prose_record_high():
    assert pp._extract_precip_inches(MAR14_SNIPPET) == 0.0


def test_mar14_max_min_from_table():
    assert pp._extract_max_temp_f(MAR14_SNIPPET) == 83.0
    assert pp._extract_min_temp_f(MAR14_SNIPPET) == 56.0
    assert pp._extract_avg_temp_f(MAR14_SNIPPET) == 69.5
    values = pp._extract_full_values(MAR14_SNIPPET)
    assert values["daily_temp_max_obs"] == 83.0
    assert values["daily_temp_max_norm"] == 70.0
    assert values["daily_temp_max_record_high"] == 93.0
    assert values["daily_temp_max_record_high_year"] == 2015
    assert values["daily_temp_max_record_low"] == 50.0
    assert values["daily_temp_max_record_low_year"] == 2025


def test_mar16_avg_not_avg_max_pdf_bleed():
    assert pp._extract_avg_temp_f(MAR16_SNIPPET) == 73.0
    assert pp._extract_max_temp_f(MAR16_SNIPPET) == 90.0
    assert pp._extract_min_temp_f(MAR16_SNIPPET) == 56.0


def test_mar16_compact_mtd_ytd_with_degree_suffix():
    values = pp._extract_full_values(MAR16_SNIPPET)
    assert values["mtd_avg_max_f_obs"] == 79.7
    assert values["mtd_avg_max_f_norm"] == 69.3
    assert values["mtd_avg_min_f_obs"] == 54.4
    assert values["mtd_avg_min_f_norm"] == 51.8
    assert values["mtd_precip_inches_obs"] == 0.0
    assert values["mtd_precip_inches_norm"] == 1.4
    assert values["mtd_cdd_obs"] == 52.0
    assert values["mtd_cdd_norm"] == 11.0
    assert values["ytd_avg_max_f_obs"] == 75.3
    assert values["ytd_precip_inches_obs"] == 6.72
    assert values["ytd_cdd_obs"] == 138.0


def test_mar10_normal_expectations_prose_fills_daily_norms():
    values = pp._extract_full_values(MAR10_PROSE_NORMS)
    assert values.get("daily_temp_max_norm") == 69.0
    assert values.get("daily_temp_min_norm") == 52.0


def test_mar17_daily_block_not_mtd_max():
    assert pp._extract_max_temp_f(MAR17_SNIPPET) == 98.0
    assert pp._extract_min_temp_f(MAR17_SNIPPET) == 64.0
    assert pp._extract_avg_temp_f(MAR17_SNIPPET) == 81.0
    values = pp._extract_full_values(MAR17_SNIPPET)
    assert values["daily_temp_max_obs"] == 98.0
    assert values["daily_temp_max_norm"] == 70.0
    assert values["daily_temp_max_record_high"] == 98.0
    assert values["daily_temp_max_record_high_year"] == 2026
    assert values["mtd_avg_max_f_obs"] == 80.8
    assert values["mtd_avg_max_f_norm"] == 69.3


def test_mar13_combined_line_precip():
    assert pp._extract_precip_inches(MAR13_COMBINED_LINE) == 0.0
    assert pp._extract_max_temp_f(MAR13_COMBINED_LINE) == 92.0
    assert pp._extract_min_temp_f(MAR13_COMBINED_LINE) == 62.0
    values = pp._extract_full_values(MAR13_COMBINED_LINE)
    assert values["daily_temp_max_obs"] == 92.0
    assert values["daily_temp_min_obs"] == 62.0
    assert values["daily_temp_avg_obs"] == 77.0
    assert values["daily_precip_inches_obs"] == 0.0


def test_mar13_record_line_extracts_record_high_low():
    values = pp._extract_full_values(MAR13_RECORD_COMBINED_LINE)
    assert values["daily_temp_max_record_high"] == 92.0
    assert values["daily_temp_max_record_high_year"] == 2026
    assert values["daily_temp_max_record_low"] == 52.0
    assert values["daily_temp_max_record_low_year"] == 1895


def test_mar18_missing_daily_returns_null_metrics():
    from pathlib import Path

    pdf_dir = Path(__file__).resolve().parents[1] / "data" / "raw" / "weather-pdfs"
    path = pdf_dir / "weather_mar18.pdf"
    if not path.exists():
        pytest.skip("sample PDF missing")
    o = pp.parse_pdf_observation(path)
    assert o is not None
    assert o.quality_flag == "missing_marked"
    assert o.temp_max_f is None
    assert o.temp_min_f is None
    assert o.temp_avg_f is None
    assert o.precip_inches is None
    assert o.hdd is None
    assert o.cdd is None
    assert o.full_values is not None
    assert o.full_values.get("daily_temp_max_norm") == 70.0
    assert o.full_values.get("daily_temp_max_record_high") == 87.0
    assert o.full_values.get("daily_temp_max_record_high_year") == 1997
    assert o.full_values.get("daily_precip_inches_obs") is None
    assert o.full_values.get("daily_precip_inches_norm") == 0.06
    assert o.full_values.get("ytd_precip_inches_obs") == 6.72
    assert o.full_values.get("ytd_hdd_obs") == 469.0
    assert o.full_values.get("ytd_cdd_obs") == 154.0


def test_mar09_ytd_not_used_for_hdd_cdd_precipitation_row():
    snippet = """
MARCH 9, 2026 WEATHER SUMMARY
Max Temperature 74 69 90(1934) 54(1917) YTD HDD: 466
YTD CDD: 101
Precipitation 0.00 0.08 2.67(1884) 0.00(2026)
Heating Degree Days 1 5 22(1893) 0(2017)
Cooling Degree Days 0 1 11(1934) 0(2026)
""".strip()
    assert pp._extract_metric(snippet, ["Heating Degree Days", "HDD"]) == 1.0
    assert pp._extract_metric(snippet, ["Cooling Degree Days", "CDD"]) == 0.0
    assert pp._extract_precip_inches(snippet) == 0.0
    values = pp._extract_full_values(snippet)
    assert values["daily_temp_max_obs"] == 74.0
    assert values["daily_temp_max_norm"] == 69.0
    assert values["daily_precip_inches_record_high"] == 2.67
    assert values["daily_hdd_obs"] == 1.0
    assert values["daily_cdd_obs"] == 0.0


def test_mar17_no_precip_line_prose_zero():
    snippet = (
        "MARCH 17, 2026\nNo precipitation was recorded.\n"
        "DAILY Avg Temp (°F) 81.0 61.3 — —\nDAILY CDD 16 1 — —\n"
    )
    assert pp._extract_precip_inches(snippet) == 0.0


def test_mar15_period_rows_extract_mtd_ytd_obs_norm():
    snippet = """
Metric Daily Obs Daily Norm Record High Record Low
Precip (in) 0.00 0.07 4.10 (2003) 0.00 (2026)
Period Avg Max Avg Min Precip CDD
MTD Obs 79.0 54.3 0.00 44
MTD Norm 69.2 51.8 1.34 10
YTD Obs 75.1 51.1 6.72 130
YTD Norm 68.2 49.9 8.27 30
""".strip()
    values = pp._extract_full_values(snippet)
    assert values["mtd_avg_max_f_obs"] == 79.0
    assert values["mtd_avg_min_f_obs"] == 54.3
    assert values["mtd_precip_inches_obs"] == 0.0
    assert values["mtd_cdd_obs"] == 44.0
    assert values["ytd_avg_max_f_norm"] == 68.2
    assert values["ytd_precip_inches_norm"] == 8.27


@pytest.mark.parametrize(
    "filename",
    [
        "weather_mar09.pdf",
        "weather_mar10.pdf",
        "weather_mar11.pdf",
        "weather_mar12.pdf",
        "weather_mar13.pdf",
        "weather_mar14.pdf",
        "weather_mar15.pdf",
        "weather_mar16.pdf",
        "weather_mar17.pdf",
        "weather_mar18.pdf",
    ],
)
def test_parse_each_sample_pdf(filename: str):
    pdf_dir = Path(__file__).resolve().parents[1] / "data" / "raw" / "weather-pdfs"
    path = pdf_dir / filename
    if not path.exists():
        pytest.skip(f"missing {path}")
    obs = pp.parse_pdf_observation(path)
    assert obs is not None
    if filename == "weather_mar18.pdf":
        assert obs.quality_flag == "missing_marked"
        assert obs.temp_max_f is None
    else:
        assert obs.temp_max_f is not None
