# Schema Overview

## Database

- Engine: SQLite
- Path: `data/weather.db`

## Tables

### `sources`

- `id` (PK, integer)
- `kind` (`csv` or `pdf`)
- `filename` (unique source filename)
- `checksum` (SHA-256 of source file)
- `ingested_at` (UTC ingestion timestamp)

### `daily_weather`

- `id` (PK, integer)
- `observation_date` (date)
- `source_id` (FK to `sources.id`)
- `temp_max_f`, `temp_min_f`, `temp_avg_f` (nullable float)
- `temp_departure` (nullable float)
- `hdd`, `cdd` (nullable float)
- `precip_inches` (nullable float)
- `snow_depth` (nullable float)
- `quality_flag` (nullable string)
- `parse_notes` (nullable text)
- `raw_excerpt` (nullable text)

Unique constraint:
- `(observation_date, source_id)` to prevent duplicate rows per source/day.

### `daily_weather_image_recognition`

- Purpose: separate full-field ingest stream from OCR over rendered PDF pages.
- Core identifiers:
  - `id` (PK, integer)
  - `observation_date` (date)
  - `source_id` (FK to `sources.id`)
  - `ingestion_type` (string, currently `image_rec`)
  - `extracted_at` (UTC timestamp)
- Traceability:
  - `quality_flag`, `parse_notes`, `raw_excerpt`, `ocr_raw_excerpt`
  - `confidence_overall` (OCR confidence summary)
  - `extraction_trace_json` (per-page structured extraction trace)
- Initial metric columns include section/metric/value families like:
  - `daily_max_temp_obs`, `daily_max_temp_norm`,
    `daily_max_temp_record_high`, `daily_max_temp_record_low`,
    `daily_max_temp_record_high_year`, `daily_max_temp_record_low_year`
  - Similar families for `min_temp`, `avg_temp`, `precip`, `hdd`, `cdd`,
    `snow_depth`, plus `mtd_*` and `ytd_*` summary families.
- Schema evolution:
  - New fields discovered during future ingest are appended with additive
    `ALTER TABLE ... ADD COLUMN`.
  - Existing columns are never dropped or renamed.

Unique constraint:
- `(observation_date, source_id, ingestion_type)` to prevent duplicate rows for
  the same source/day/method.

## Assumptions

- Temperature is represented in Fahrenheit (`_f` suffix in schema).
- Precipitation and snow are represented in inches.
- If values are malformed (`M`, `ERROR`, `NO WEATHER`, percent text), numeric
  fields are stored as null and traceability goes to `quality_flag`,
  `parse_notes`, and `raw_excerpt`.
- CSV and PDF rows are intentionally kept as separate observations via
  `source_id` so overlap can be analyzed.
- Existing `daily_weather` ingest remains unchanged; image-recognition values
  are isolated in `daily_weather_image_recognition` for side-by-side comparison.
- `daily_weather` remains parser-driven and statically modeled today; additive
  schema evolution is currently applied to `daily_weather_image_recognition`.
- The wide-month CSV can mis-align commas (e.g. some February rows with empty
  CDD); `inspect_db.sh` may still flag rare values such as **2026-02-27** high
  `precip_inches` from the CSV slice—treat as source ambiguity, not PDF layout.
