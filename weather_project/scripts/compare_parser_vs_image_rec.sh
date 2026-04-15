#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${WEATHER_DB:-data/weather.db}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found: $DB_PATH"
  echo "Run: poetry run ingest-weather && poetry run ingest-weather-image-recognition"
  exit 1
fi

sqlite3 -header -column "$DB_PATH" "
WITH parser AS (
  SELECT
    d.observation_date,
    d.source_id,
    s.filename,
    d.temp_max_f AS parser_temp_max_f,
    d.temp_min_f AS parser_temp_min_f,
    d.temp_avg_f AS parser_temp_avg_f,
    d.precip_inches AS parser_precip_inches,
    d.hdd AS parser_hdd,
    d.cdd AS parser_cdd
  FROM daily_weather d
  JOIN sources s ON s.id = d.source_id
  WHERE s.kind = 'pdf'
),
img AS (
  SELECT
    observation_date,
    source_id,
    daily_max_temp_obs AS image_temp_max_f,
    daily_min_temp_obs AS image_temp_min_f,
    daily_avg_temp_obs AS image_temp_avg_f,
    daily_precip_obs AS image_precip_inches,
    daily_hdd_obs AS image_hdd,
    daily_cdd_obs AS image_cdd
  FROM daily_weather_image_recognition
  WHERE ingestion_type = 'image_rec'
)
SELECT
  p.observation_date,
  p.filename,
  p.parser_temp_max_f,
  i.image_temp_max_f,
  CASE WHEN p.parser_temp_max_f IS NULL OR i.image_temp_max_f IS NULL THEN NULL
       ELSE ROUND(ABS(p.parser_temp_max_f - i.image_temp_max_f), 3)
  END AS delta_temp_max,
  p.parser_temp_min_f,
  i.image_temp_min_f,
  CASE WHEN p.parser_temp_min_f IS NULL OR i.image_temp_min_f IS NULL THEN NULL
       ELSE ROUND(ABS(p.parser_temp_min_f - i.image_temp_min_f), 3)
  END AS delta_temp_min,
  p.parser_temp_avg_f,
  i.image_temp_avg_f,
  CASE WHEN p.parser_temp_avg_f IS NULL OR i.image_temp_avg_f IS NULL THEN NULL
       ELSE ROUND(ABS(p.parser_temp_avg_f - i.image_temp_avg_f), 3)
  END AS delta_temp_avg,
  p.parser_precip_inches,
  i.image_precip_inches,
  CASE WHEN p.parser_precip_inches IS NULL OR i.image_precip_inches IS NULL THEN NULL
       ELSE ROUND(ABS(p.parser_precip_inches - i.image_precip_inches), 3)
  END AS delta_precip,
  p.parser_hdd,
  i.image_hdd,
  CASE WHEN p.parser_hdd IS NULL OR i.image_hdd IS NULL THEN NULL
       ELSE ROUND(ABS(p.parser_hdd - i.image_hdd), 3)
  END AS delta_hdd,
  p.parser_cdd,
  i.image_cdd,
  CASE WHEN p.parser_cdd IS NULL OR i.image_cdd IS NULL THEN NULL
       ELSE ROUND(ABS(p.parser_cdd - i.image_cdd), 3)
  END AS delta_cdd
FROM parser p
LEFT JOIN img i
  ON i.observation_date = p.observation_date
 AND i.source_id = p.source_id
ORDER BY p.observation_date;
"
