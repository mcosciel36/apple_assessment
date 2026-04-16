#!/usr/bin/env bash
# Smoke test / initial data-quality inspection for weather SQLite DB.
# Usage (from anywhere):
#   ./scripts/inspect_db.sh
#   ./scripts/inspect_db.sh > stdout.txt   # see README: column output is clearer in a file
#   WEATHER_DB=/path/to/weather.db ./scripts/inspect_db.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DB="${WEATHER_DB:-${PROJECT_ROOT}/data/weather.db}"

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
run_sql "SQLite version" "select sqlite_version() as sqlite_version;"

run_sql "Row counts" "
select 'sources' as tbl, count(*) as n from sources
union all
select 'daily_weather', count(*) from daily_weather;
"

run_sql "Sources (kind, file, ingested)" "
select id, kind, filename, substr(checksum, 1, 12) || '…' as checksum_prefix, ingested_at
from sources
order by kind, id;
"

run_sql "Observations by source kind" "
select s.kind, count(*) as observation_rows
from daily_weather d
join sources s on s.id = d.source_id
group by s.kind
order by s.kind;
"

run_sql "Observation date range" "
select
  min(observation_date) as min_date,
  max(observation_date) as max_date
from daily_weather;
"

run_sql "Quality flags (non-null)" "
select coalesce(quality_flag, '(null)') as quality_flag, count(*) as n
from daily_weather
group by quality_flag
order by n desc;
"

run_sql "Missing key metrics (nulls)" "
select
  sum(case when temp_max_f is null then 1 else 0 end) as null_temp_max,
  sum(case when temp_min_f is null then 1 else 0 end) as null_temp_min,
  sum(case when temp_avg_f is null then 1 else 0 end) as null_temp_avg,
  sum(case when precip_inches is null then 1 else 0 end) as null_precip
from daily_weather;
"

run_sql "Duplicate (date, source) rows (expect 0)" "
select observation_date, source_id, count(*) as cnt
from daily_weather
group by observation_date, source_id
having count(*) > 1;
"

run_sql "Same calendar date from CSV and PDF (overlap days)" "
select d.observation_date, count(distinct s.kind) as source_kinds
from daily_weather d
join sources s on s.id = d.source_id
group by d.observation_date
having count(distinct s.kind) > 1
order by d.observation_date;
"

run_sql "DQ: suspicious daily precipitation (heuristic > 3 in)" "
select d.observation_date, s.kind, s.filename,
  d.precip_inches, d.temp_max_f, d.temp_avg_f,
  d.quality_flag
from daily_weather d
join sources s on s.id = d.source_id
where d.precip_inches is not null and d.precip_inches > 3
order by d.precip_inches desc, d.observation_date, s.kind;
"

run_sql "DQ: min temp greater than max temp (expect empty)" "
select d.observation_date, s.kind, s.filename,
  d.temp_min_f, d.temp_max_f, d.precip_inches
from daily_weather d
join sources s on s.id = d.source_id
where d.temp_min_f is not null and d.temp_max_f is not null
  and d.temp_min_f > d.temp_max_f
order by d.observation_date, s.kind;
"

run_sql "DQ: CSV vs PDF field deltas on same calendar date" "
with paired as (
  select d.observation_date,
    max(case when s.kind = 'csv' then d.precip_inches end) as csv_precip,
    max(case when s.kind = 'pdf' then d.precip_inches end) as pdf_precip,
    max(case when s.kind = 'csv' then d.temp_max_f end) as csv_tmax,
    max(case when s.kind = 'pdf' then d.temp_max_f end) as pdf_tmax,
    max(case when s.kind = 'csv' then d.temp_min_f end) as csv_tmin,
    max(case when s.kind = 'pdf' then d.temp_min_f end) as pdf_tmin,
    max(case when s.kind = 'csv' then d.temp_avg_f end) as csv_tavg,
    max(case when s.kind = 'pdf' then d.temp_avg_f end) as pdf_tavg
  from daily_weather d
  join sources s on s.id = d.source_id
  group by d.observation_date
  having count(distinct s.kind) > 1
)
select observation_date,
  csv_precip, pdf_precip,
  round(abs(coalesce(csv_precip, 0) - coalesce(pdf_precip, 0)), 3) as precip_abs_delta,
  csv_tmax, pdf_tmax,
  round(abs(coalesce(csv_tmax, 0) - coalesce(pdf_tmax, 0)), 2) as tmax_abs_delta,
  csv_tmin, pdf_tmin,
  round(abs(coalesce(csv_tmin, 0) - coalesce(pdf_tmin, 0)), 2) as tmin_abs_delta,
  csv_tavg, pdf_tavg,
  round(abs(coalesce(csv_tavg, 0) - coalesce(pdf_tavg, 0)), 2) as tavg_abs_delta
from paired
where abs(coalesce(csv_precip, 0) - coalesce(pdf_precip, 0)) > 0.05
   or abs(coalesce(csv_tmax, 0) - coalesce(pdf_tmax, 0)) > 0.5
   or abs(coalesce(csv_tmin, 0) - coalesce(pdf_tmin, 0)) > 0.5
   or abs(coalesce(csv_tavg, 0) - coalesce(pdf_tavg, 0)) > 0.5
order by precip_abs_delta desc, observation_date;
"

run_sql "DQ: PDF rows only — precip vs nearby temps (possible label bleed)" "
select d.observation_date, s.filename,
  d.temp_avg_f, d.precip_inches,
  case when d.temp_avg_f is not null and d.precip_inches is not null
       and abs(d.precip_inches - d.temp_avg_f) < 0.25 then 'precip ~= avg_temp'
       else '' end as note
from daily_weather d
join sources s on s.id = d.source_id
where s.kind = 'pdf'
  and d.precip_inches is not null
  and d.temp_avg_f is not null
  and abs(d.precip_inches - d.temp_avg_f) < 0.25
  and d.precip_inches > 0.01
order by d.observation_date;
"

run_sql "Sample joined rows (5)" "
select
  d.observation_date,
  s.kind,
  s.filename,
  d.temp_max_f,
  d.temp_min_f,
  d.precip_inches,
  d.quality_flag
from daily_weather d
join sources s on s.id = d.source_id
order by d.observation_date, s.kind
limit 5;
"

run_sql "Full daily_weather dump (all columns, all rows)" "
select *
from daily_weather
order by observation_date, source_id;
"

echo ""
echo "=== Done ==="
echo "Duplicate (date, source): should be empty (unique index on daily_weather)."
echo "Overlap days: dates where both csv and pdf contributed a row (expected for March PDF window)."
echo "DQ precip > 3 in: rare for LA; large values often indicate PDF field bleed (fixed in parser)."
echo "DQ CSV vs PDF deltas: on overlap days, material mismatches may indicate parsing or source drift."
echo "DQ precip ~= avg_temp: heuristic for mistaken token bind (same numeric field on one PDF line)."
