# Image vs SQLite sign-off — March 9–18, 2026 (PDF screenshots)

**Date:** 2026-04-15  
**Method:** Values read from `data/raw/daily_images/march_9.png` … `march_18.png` (via image review) and cross-checked against `data/weather.db` after `poetry run ingest-weather`. Ambiguous screenshot rows were confirmed against extracted PDF text (`data/raw/weather-pdfs/weather_mar*.pdf`) where noted. No Tesseract pipeline.

**Query used (subset of `docs/llm_image_db_validation.md`):** PDF rows `sources.kind = 'pdf'`, `observation_date` between `2026-03-09` and `2026-03-18`.

**Overall:** **PASS** — All **daily** and **MTD** fields that are both visible on the images and stored in SQLite match within normal float rounding (`±0.01` for decimals, integer temps/HDD/CDD exact). **Mar 18** matches the documented **missing daily obs** pattern (`quality_flag = missing_marked`, null legacy dailies, normals + **YTD** totals populated). **Mar 16** shows **YTD average max/min** on the PDF/screenshot; those prose values are **not** present as dedicated columns on the `2026-03-16` row (only **YTD precip** and **YTD CDD** are stored among YTD metrics for that day in the current schema)—treated as **scope / schema**, not an ingest error for the fields we do persist.

---

## Per-day matrix

| Date | PNG | Daily obs/norm (temps, precip, HDD/CDD where shown) | Records (where shown) | MTD block | YTD / footer | DB `quality_flag` | Result |
|------|-----|--------------------------------------------------------|-------------------------|-----------|--------------|-------------------|--------|
| 2026-03-09 | march_9.png | Matches | Matches | N/A on page | N/A on page | `qc_0` | **PASS** |
| 2026-03-10 | march_10.png | Matches (prose + table) | N/A | N/A | N/A | (null) | **PASS** |
| 2026-03-11 | march_11.png | Matches (min 51 ↔ 51.0 float) | Matches | MTD Avg Max/Min/Precip obs+norm match | N/A | `qc_0` | **PASS** |
| 2026-03-12 | march_12.png | Matches | Matches | N/A | N/A | (null) | **PASS** |
| 2026-03-13 | march_13.png | Daily + records match | — | MTD incl. **Avg Min obs 54.1** (PDF text confirms; one screenshot read misread 53.2) | N/A | (null) | **PASS** |
| 2026-03-14 | march_14.png | Matches (avg norm 61.0 ↔ 61.0) | Matches | N/A | N/A | (null) | **PASS** |
| 2026-03-15 | march_15.png | Matches | Matches | MTD row matches | YTD precip **6.72**, CDD **130** match | `qc_0` | **PASS** |
| 2026-03-16 | march_16.png | Daily + MTD match | N/A | MTD matches | **YTD precip 6.72**, **CDD 138** match DB; YTD Avg Max/Min on page **not** in DB columns | (null) | **PASS** (see note) |
| 2026-03-17 | march_17.png | Matches incl. CDD 16/1 | Matches | MTD Avg Max/Min/CDD match | N/A | (null) | **PASS** |
| 2026-03-18 | march_18.png | All daily **M** → null obs in DB; normals 70/53/61.3/0.06/HDD4/CDD1 match | Matches | N/A | YTD precip **6.72**, HDD **469**, CDD **154**, Avg Temp **63.5** ↔ `ytd_temp_avg_obs` **63.5** | `missing_marked` | **PASS** |

---

## Mar 16 — YTD averages (scope note)

Screenshot/PDF include **YTD Obs** for Avg Max **75.3°F**, Avg Min **51.2°F** (and norm pairs). The ingested row for 2026-03-16 includes **`ytd_precip_inches_obs`** and **`ytd_cdd_obs`** consistent with the same tables; **YTD average temperature statistics** for that layout are not duplicated as separate nullable columns on this row in the current model. Reviewers validating “every pixel” should treat that as **documentation/schema coverage**, not a failure of precip/CDD YTD ingestion.

---

## Commands run (reproducibility)

```bash
cd weather_project
poetry run ingest-weather
poetry run pytest -q   # 22 passed at time of sign-off
```

SQLite: use the full `SELECT` in `docs/llm_image_db_validation.md` for the same window.

---

## Sign-off

- **Ingest:** OK for this dataset.  
- **Automated tests:** `pytest` green (22 tests).  
- **Image ↔ DB (Mar 9–18):** **PASS** for all stored fields visible on the PNGs, with the Mar 16 YTD-average column scope noted above.

Signed off in-repo: this file + commit history on branch `main` as of ingest run dated in header.
