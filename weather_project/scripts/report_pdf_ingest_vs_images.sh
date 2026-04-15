#!/usr/bin/env bash
# PDF parser ingest report + image cross-check
# Usage:
#   ./scripts/report_pdf_ingest_vs_images.sh
#   WEATHER_DB=/path/to/weather.db IMAGE_DIR=/path/to/daily_images ./scripts/report_pdf_ingest_vs_images.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DB="${WEATHER_DB:-${PROJECT_ROOT}/data/weather.db}"
IMAGE_DIR="${IMAGE_DIR:-${PROJECT_ROOT}/data/raw/daily_images}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "error: sqlite3 not found on PATH" >&2
  exit 1
fi

if [[ ! -f "${DB}" ]]; then
  echo "error: database file not found: ${DB}" >&2
  echo "hint: run 'poetry run ingest-weather' from ${PROJECT_ROOT} first" >&2
  exit 1
fi

run_sql() {
  local title="$1"
  local sql="$2"
  echo ""
  echo "=== ${title} ==="
  sqlite3 -header -column "${DB}" "${sql}"
}

echo "Database: ${DB}"
echo "Image directory: ${IMAGE_DIR}"

run_sql "PDF rows summary (legacy + full-column sample)" "
select
  d.observation_date,
  s.filename as pdf_file,
  d.temp_max_f,
  d.temp_min_f,
  d.temp_avg_f,
  d.precip_inches,
  d.daily_temp_max_obs,
  d.daily_temp_max_norm,
  d.daily_temp_max_record_high,
  d.daily_temp_max_record_high_year,
  d.mtd_avg_max_f_obs,
  d.mtd_avg_max_f_norm,
  d.ytd_avg_max_f_obs,
  d.ytd_avg_max_f_norm,
  d.quality_flag
from daily_weather d
join sources s on s.id = d.source_id
where s.kind = 'pdf'
order by d.observation_date;
"

run_sql "PDF null coverage counts" "
select
  count(*) as pdf_rows,
  sum(case when temp_max_f is null then 1 else 0 end) as null_temp_max_f,
  sum(case when temp_min_f is null then 1 else 0 end) as null_temp_min_f,
  sum(case when temp_avg_f is null then 1 else 0 end) as null_temp_avg_f,
  sum(case when precip_inches is null then 1 else 0 end) as null_precip_inches,
  sum(case when daily_temp_max_obs is null then 1 else 0 end) as null_daily_temp_max_obs,
  sum(case when daily_temp_max_norm is null then 1 else 0 end) as null_daily_temp_max_norm,
  sum(case when mtd_avg_max_f_obs is null then 1 else 0 end) as null_mtd_avg_max_obs,
  sum(case when ytd_avg_max_f_obs is null then 1 else 0 end) as null_ytd_avg_max_obs
from daily_weather d
join sources s on s.id = d.source_id
where s.kind = 'pdf';
"

run_sql "PDF full-column extraction coverage by section" "
select
  sum(case when daily_temp_max_obs is not null
         or daily_temp_min_obs is not null
         or daily_temp_avg_obs is not null
         or daily_precip_inches_obs is not null then 1 else 0 end) as rows_with_daily_values,
  sum(case when mtd_avg_max_f_obs is not null
         or mtd_avg_min_f_obs is not null
         or mtd_temp_avg_obs is not null
         or mtd_precip_inches_obs is not null then 1 else 0 end) as rows_with_mtd_values,
  sum(case when ytd_avg_max_f_obs is not null
         or ytd_avg_min_f_obs is not null
         or ytd_temp_avg_obs is not null
         or ytd_precip_inches_obs is not null then 1 else 0 end) as rows_with_ytd_values
from daily_weather d
join sources s on s.id = d.source_id
where s.kind = 'pdf';
"

run_sql "PDF rows with possible DQ signal (obs missing but norm/record present)" "
select
  d.observation_date,
  s.filename as pdf_file,
  d.daily_temp_max_obs,
  d.daily_temp_max_norm,
  d.daily_temp_max_record_high,
  d.daily_temp_max_record_high_year,
  d.quality_flag,
  d.parse_notes
from daily_weather d
join sources s on s.id = d.source_id
where s.kind = 'pdf'
  and d.daily_temp_max_obs is null
  and (
    d.daily_temp_max_norm is not null
    or d.daily_temp_max_record_high is not null
    or d.daily_temp_max_record_low is not null
  )
order by d.observation_date;
"

echo ""
echo "=== Image match check (by date token in PDF filename) ==="
if [[ ! -d "${IMAGE_DIR}" ]]; then
  echo "warning: image directory not found: ${IMAGE_DIR}"
  exit 0
fi

image_count="$(ls -1 "${IMAGE_DIR}" 2>/dev/null | wc -l | tr -d ' ')"
if [[ "${image_count}" == "0" ]]; then
  echo "warning: no image files found in ${IMAGE_DIR}"
  exit 0
fi

sqlite3 -separator '|' "${DB}" "
select d.observation_date, s.filename
from daily_weather d
join sources s on s.id = d.source_id
where s.kind = 'pdf'
order by d.observation_date;
" | while IFS='|' read -r obs_date pdf_file; do
  token="$(echo "${pdf_file}" | tr '[:upper:]' '[:lower:]' | sed -E 's/.*mar([0-9]{2}).*/mar\1/')"
  matches="$(ls -1 "${IMAGE_DIR}" 2>/dev/null | awk '{print tolower($0)}' | awk -v tok="${token}" 'index($0, tok) > 0')"
  match_count="$(echo "${matches}" | sed '/^$/d' | wc -l | tr -d ' ')"
  echo "${obs_date} | ${pdf_file} | image_matches=${match_count}"
  if [[ "${match_count}" -gt 0 ]]; then
    echo "${matches}" | sed '/^$/d' | sed 's/^/  - /'
  fi
done

echo ""
echo "=== Done ==="
