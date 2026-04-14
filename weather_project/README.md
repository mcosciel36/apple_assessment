# Apple Weather Project

This project implements a repeatable weather ingestion pipeline and a notebook
analysis for Downtown LA weather.

## Prerequisites

- [asdf](https://asdf-vm.com/) with the [Python plugin](https://github.com/asdf-community/asdf-python)
- [Poetry](https://python-poetry.org/) (install globally or via asdf)

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
   - `poetry run ingest-weather`
3. Open the analysis notebook:
   - `poetry run jupyter notebook notebooks/weather_analysis.ipynb`

## Data inputs

- `../archive/3month_weather.csv`
- `../archive/weather-pdfs.zip`

The pipeline unzips PDFs into `data/raw/weather-pdfs` and writes SQLite output
to `data/weather.db`.

## Project layout

- `src/weather_project/ingest.py`: end-to-end ingestion entrypoint
- `src/weather_project/parsers/csv_parser.py`: section-aware CSV parser
- `src/weather_project/parsers/pdf_parser.py`: resilient PDF parser
- `notebooks/weather_analysis.ipynb`: analysis with at least three charts
- `docs/schema.md`: schema and assumption overview

## Notes on data quality

- The CSV includes malformed rows and placeholders (`ERROR`, `NO WEATHER`, `M`).
- The parser stores these as null numeric values and sets `quality_flag`.
- PDF layouts vary by day; the parser uses flexible text matching and date
  pattern fallbacks to keep ingestion robust.
