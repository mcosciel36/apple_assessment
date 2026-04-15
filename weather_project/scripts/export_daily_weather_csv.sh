#!/usr/bin/env bash
# Export full daily_weather table to CSV for visual inspection.
# Usage:
#   ./scripts/export_daily_weather_csv.sh
#   WEATHER_DB=/path/to/weather.db OUT_CSV=/path/to/out.csv ./scripts/export_daily_weather_csv.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DB="${WEATHER_DB:-${PROJECT_ROOT}/data/weather.db}"
OUT_CSV="${OUT_CSV:-${PROJECT_ROOT}/data/processed/daily_weather_all_rows.csv}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "error: sqlite3 not found on PATH" >&2
  exit 1
fi

if [[ ! -f "${DB}" ]]; then
  echo "error: database file not found: ${DB}" >&2
  echo "hint: run 'poetry run ingest-weather' from ${PROJECT_ROOT} first" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUT_CSV}")"

sqlite3 -header -csv "${DB}" "
select *
from daily_weather
order by observation_date, source_id;
" > "${OUT_CSV}"

echo "Wrote CSV: ${OUT_CSV}"
