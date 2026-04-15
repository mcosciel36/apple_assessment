# Apple Weather Project

This project implements a repeatable weather ingestion pipeline and a notebook
analysis for Downtown LA weather.

## Prerequisites

- [asdf](https://asdf-vm.com/) with the [Python plugin](https://github.com/asdf-community/asdf-python)
- [Poetry](https://python-poetry.org/) (install globally or via asdf)
- `sqlite3` on your `PATH` for the optional smoke script (included on macOS;
  on Linux install your distro’s `sqlite` / `sqlite3` package if needed)
- `tesseract` on your `PATH` for OCR-based image-recognition ingest
  (`ingest-weather-image-recognition`)

Python is pinned in [`.tool-versions`](.tool-versions) to match `pyproject.toml`
(`>=3.10,<3.13`). Use asdf so the correct interpreter is active in this directory.

Install Tesseract (system dependency, not a Poetry package):

```bash
brew install tesseract
tesseract --version
```

`tesseract` cannot be added as a Python dependency in `pyproject.toml`; it is
a native OCR binary installed at the OS level.

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
   - `poetry run ingest-weather`  
     This writes `data/weather.db` (and refreshes extracted PDFs under `data/raw/`).
   - Optional image-recognition ingest:
     - `poetry run ingest-weather-image-recognition`
     - This writes to `daily_weather_image_recognition` and does **not** change
       `daily_weather` rows produced by `ingest-weather`.
   - Compare parser vs image-recognition rows:
     - `./scripts/compare_parser_vs_image_rec.sh`
3. **Smoke test / data-quality check (after ingest):**  
   Run this **after** step 2 so `data/weather.db` exists. It uses the system
   `sqlite3` CLI (no Poetry) to print row counts, source breakdown, date range,
   `quality_flag` distribution, null metrics, duplicate-key check, and CSV vs
   PDF date overlap.

   ```bash
   ./scripts/inspect_db.sh
   ```

   Use a different DB file:  
   `WEATHER_DB=/path/to/weather.db ./scripts/inspect_db.sh`
4. Open the analysis notebook:
   - `poetry run jupyter notebook notebooks/weather_analysis.ipynb`

## Data inputs

- `../archive/3month_weather.csv`
- `../archive/weather-pdfs.zip`

The pipeline unzips PDFs into `data/raw/weather-pdfs` and writes SQLite output
to `data/weather.db`. Re-run step 2 whenever inputs change; then re-run step 3
if you want a fresh CLI sanity check.

## Project layout

- `scripts/inspect_db.sh`: SQLite CLI smoke test (row counts, quality flags, overlaps)
- `tests/test_pdf_parser_snippets.py`: PDF parser regression (Mar 13–17 layout cases)
- `tests/test_image_recognition_ingest.py`: image-recognition ingest/regression tests
- `src/weather_project/ingest.py`: end-to-end ingestion entrypoint
- `src/weather_project/ingest_image_recognition.py`: separate OCR ingest from rendered PDF pages
- `src/weather_project/parsers/csv_parser.py`: section-aware CSV parser
- `src/weather_project/parsers/pdf_parser.py`: resilient PDF parser
- `src/weather_project/parsers/pdf_image_recognition_parser.py`: OCR full-field parser over rendered PDF pages
- `notebooks/weather_analysis.ipynb`: analysis with at least three charts
- `docs/schema.md`: schema and assumption overview

## Notes on data quality

- The CSV includes malformed rows and placeholders (`ERROR`, `NO WEATHER`, `M`).
- The parser stores these as null numeric values and sets `quality_flag`.
- PDF layouts vary by day; the parser uses flexible text matching and date
  pattern fallbacks to keep ingestion robust.
- The image-recognition ingest writes OCR-derived values to
  `daily_weather_image_recognition` and keeps parser output in `daily_weather`.
- Image-recognition rows include confidence/trace metadata
  (`confidence_overall`, `extraction_trace_json`, `ocr_raw_excerpt`) for audit.
