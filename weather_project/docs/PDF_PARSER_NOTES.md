# PDF parser DQ fixes (applied)

**Implementation:** [`src/weather_project/parsers/pdf_parser.py`](../src/weather_project/parsers/pdf_parser.py)  
**Regression tests:** [`tests/test_pdf_parser_snippets.py`](../tests/test_pdf_parser_snippets.py)

**What changed:**

1. **`_extract_precip_inches`** — `Precip (in)`, `Precip … in`, then tokenized `Precip 0.00` rows (avoids prose `precipitation` → record-high °F bleed).
2. **`_extract_max_temp_f` / `_extract_min_temp_f`** — Line-anchored `Max (°F)` / `Min (°F)` and `Max 90°F` style; skip `MTD` / lines starting with `Avg Max` or `Avg Min`; `DAILY` value after `Max Temp` / `Min Temp`.
3. **`_extract_avg_temp_f`** — `DAILY Avg Temp` line; `Avg (°F) 69.5` / `Avg 73.0°F` patterns; skip only lines that **start** with `Avg Max` / `Avg Min` / `MTD`.
4. **`_extract_metric` (HDD/CDD)** — Ignore matches where **`ytd`** appears before the label on the same line (fixes Mar 9: `Max Temperature … YTD HDD: 466` bleed into HDD).
5. **`_extract_precip_inches`** — Line-anchored **`Precipitation 0.00`** table rows; prose **`no precipitation`** → `0.0` when no structured precip line (e.g. Mar 17).
6. **All daily observations MISSING (M)** — When the PDF states that (Mar 18), return **all daily metrics null** with `quality_flag=missing_marked` so normals/record blocks are not ingested as observed.

**Ingestion:** There is **no** separate “failed PDF” table. If `parse_pdf_observation` returns **`None`** (e.g. no date), the file is **skipped** with a log warning only. Otherwise one row is written to **`daily_weather`** (possibly with nulls + flags).

Run **`poetry run pytest`** and **`poetry run python -m weather_project.ingest`** after parser changes.
