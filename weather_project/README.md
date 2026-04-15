# Apple Weather Project

This project implements a repeatable weather ingestion pipeline and notebook
analysis for Downtown LA weather (CSV + PDF sources).

## Prerequisites

- [asdf](https://asdf-vm.com/) with the [Python plugin](https://github.com/asdf-community/asdf-python)
- [Poetry](https://python-poetry.org/) (install globally or via asdf)
- `sqlite3` on your `PATH` for the optional smoke scripts (included on macOS;
  on Linux install your distro’s `sqlite` / `sqlite3` package if needed)

Python is pinned in [`.tool-versions`](.tool-versions) to match `pyproject.toml`
(`>=3.10,<3.13`). Use asdf so the correct interpreter is active in this directory.

## Quick start

This Poetry package lives beside the `archive/` folder. From the **assessment
repository root** (the directory that contains both `archive/` and
`weather_project/`):

```bash
cd weather_project
```

You are then in the directory that contains `pyproject.toml` and `.tool-versions`.

Install the pinned Python (and activate it for this path):

```bash
asdf install
```

1. Install dependencies:
   - `poetry install`
2. Build and load the database:
   - `poetry run ingest-weather` (same as `poetry run python -m weather_project.ingest`)  
     This writes `data/weather.db` (and refreshes extracted PDFs under `data/raw/`).
     Ingest sets `ingestion_type` on each row (`csv` or `pdf`) for easy filtering.
     PDF ingestion fills legacy observed columns (`temp_max_f`, etc.) and additive
     full-parser columns (`daily_*`, `mtd_*`, `ytd_*` obs/norm/record/year where parsed).
     The PDF parser handles several layout variants (including prose normals on Mar 10,
     compact MTD/YTD tables with `°F` on Mar 16, split-line YTD HDD/CDD on Mar 18, and
     all-daily-`M` rows without mis-attributing YTD precip to daily obs).
3. **Smoke test / data-quality check (after ingest):**  
   Run this **after** step 2 so `data/weather.db` exists. It uses the system
   `sqlite3` CLI (no Poetry) to print row counts, source breakdown, date range,
   `quality_flag` distribution, null metrics, duplicate-key check, CSV vs
   PDF overlap, a full `daily_weather` dump, and more.

   ```bash
   ./scripts/inspect_db.sh
   ```

   Use a different DB file:  
   `WEATHER_DB=/path/to/weather.db ./scripts/inspect_db.sh`

   **Export all `daily_weather` rows to CSV** (easier to open in Sheets than wide terminal output):

   ```bash
   ./scripts/export_daily_weather_csv.sh
   ```

   Default output: `data/processed/daily_weather_all_rows.csv`  
   Override: `OUT_CSV=/path/to/out.csv ./scripts/export_daily_weather_csv.sh`

   **PDF-focused SQL report** (optional; compares parser fields and lists image filename hints):

   - `./scripts/report_pdf_ingest_vs_images.sh`
   - `IMAGE_DIR=/path/to/daily_images ./scripts/report_pdf_ingest_vs_images.sh`

## Screenshot vs database checks (LLM-friendly)

Step-by-step instructions for comparing **`data/raw/daily_images/march_*.png`** to **`data/weather.db`** (no Tesseract), plus a **copy-paste prompt** for Cursor or other assistants, live in:

**[`docs/llm_image_db_validation.md`](docs/llm_image_db_validation.md)**

Typical usage: after ingest, open a chat in this repo and prompt along the lines of:

```text
@weather_project/docs/llm_image_db_validation.md
Re-run the image vs SQLite comparison for March 9–18, 2026. Do not use OCR;
use the screenshots under data/raw/daily_images/ and the PDF rows in data/weather.db.
```

Adjust the `@` path if your editor roots the workspace above `weather_project/`.

4. **Open the main analysis notebook** (observed vs normal vs records, CSV vs PDF):

   ```bash
   poetry run jupyter notebook notebooks/weather_analysis_full_columns.ipynb
   ```

   Run Jupyter from the `weather_project/` directory so notebook paths like `../data/weather.db` resolve.

   **Which notebook to use**
   - **`weather_analysis_full_columns.ipynb` (recommended)** — PDF-focused `daily_*` columns,
     CSV vs PDF deltas on legacy fields, optional “image truth” reconciliation for March PDFs,
     and charts (temps vs normal/record, HDD/CDD, precip). Use this for the take-home deep dive.
   - **`weather_analysis.ipynb`** — shorter notebook: **all** `daily_weather` rows joined to
     `sources`, monthly temperature trend, wet-day precip distribution, and quality/source
     summaries. It does **not** use expanded `daily_*` / `mtd_*` / `ytd_*` columns; it is a
     broader, lighter-weight EDA over the same database.
   - **`weather_analysisV1_origObsOnly.ipynb`** — older observed-only snapshot.

## Data inputs

- `../archive/3month_weather.csv`
- `../archive/weather-pdfs.zip`

The pipeline unzips PDFs into `data/raw/weather-pdfs` and writes SQLite output
to `data/weather.db`. Re-run step 2 whenever inputs change; then re-run step 3
if you want a fresh CLI sanity check or CSV export.

## Project layout

- `scripts/inspect_db.sh`: SQLite CLI smoke test and full-table dump
- `scripts/export_daily_weather_csv.sh`: export `select * from daily_weather` to CSV
- `scripts/report_pdf_ingest_vs_images.sh`: PDF row report + image path hints
- `tests/test_pdf_parser_snippets.py`: PDF parser regression (layout edge cases)
- `src/weather_project/ingest.py`: end-to-end ingestion (`csv` + `pdf`)
- `src/weather_project/parsers/csv_parser.py`: section-aware CSV parser
- `src/weather_project/parsers/pdf_parser.py`: PDF text parser (observed + `daily_*` / `mtd_*` / `ytd_*` where applicable)
- `notebooks/weather_analysis_full_columns.ipynb`: **primary** analysis (CSV vs PDF, normals, records)
- `notebooks/weather_analysis.ipynb`: earlier notebook (core metrics)
- `docs/schema.md`: schema and assumptions (`ingestion_type`, additive columns)
- `docs/llm_image_db_validation.md`: how to compare screenshots to SQLite + LLM prompt template

## Notes on data quality

- The CSV includes malformed rows and placeholders (`ERROR`, `NO WEATHER`, `M`).
- The parser stores these as null numeric values and sets `quality_flag`.
- PDF layouts vary by day; the parser uses flexible text matching and date
  pattern fallbacks to keep ingestion robust. Expanded norm/record columns may be
  null when the source layout does not expose those fields in a parseable row.
