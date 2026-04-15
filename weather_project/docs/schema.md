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
- `ingestion_type` (`csv` or `pdf`; nullable for backward compatibility)
- `temp_max_f`, `temp_min_f`, `temp_avg_f` (nullable float)
- `temp_departure` (nullable float)
- `hdd`, `cdd` (nullable float)
- `precip_inches` (nullable float)
- `snow_depth` (nullable float)
- `quality_flag` (nullable string)
- `parse_notes` (nullable text)
- `raw_excerpt` (nullable text)
- Additive parser-detail column families (all nullable):
  - `daily_*`: full daily extraction fields like
    `daily_temp_max_obs`, `daily_temp_max_norm`,
    `daily_temp_max_record_high`, `daily_temp_max_record_high_year`,
    `daily_temp_max_record_low`, `daily_temp_max_record_low_year`
    (same pattern for min/avg/precip/hdd/cdd/snow_depth where present)
  - `mtd_*`: month-to-date fields such as
    `mtd_avg_max_f_obs`, `mtd_avg_max_f_norm`,
    `mtd_avg_max_f_record_high`, `mtd_avg_max_f_record_high_year`,
    `mtd_avg_max_f_record_low`, `mtd_avg_max_f_record_low_year`
    (same pattern for avg_min/temp_avg/precip/hdd/cdd where present)
  - `ytd_*`: year-to-date fields with the same obs/norm/record/year pattern

Unique constraint:
- `(observation_date, source_id)` to prevent duplicate rows per source/day.

Schema evolution policy:
- `daily_weather` uses additive schema evolution during ingest (`ALTER TABLE ADD COLUMN`),
  so newly introduced parser fields can be added without dropping/replacing the table.

## Assumptions

- Temperature is represented in Fahrenheit (`_f` suffix in schema).
- Precipitation and snow are represented in inches.
- If values are malformed (`M`, `ERROR`, `NO WEATHER`, percent text), numeric
  fields are stored as null and traceability goes to `quality_flag`,
  `parse_notes`, and `raw_excerpt`.
- CSV and PDF rows are intentionally kept as separate observations via
  `source_id` so overlap can be analyzed.
- The wide-month CSV can mis-align commas (e.g. some February rows with empty
  CDD); `inspect_db.sh` may still flag rare values such as **2026-02-27** high
  `precip_inches` from the CSV slice—treat as source ambiguity, not PDF layout.
