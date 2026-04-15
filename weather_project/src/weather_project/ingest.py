from __future__ import annotations

import hashlib
import logging
import zipfile
from pathlib import Path

from sqlalchemy import Integer, String, Text

from weather_project.config import get_settings
from weather_project.db import (
    create_schema,
    ensure_daily_weather_columns,
    get_or_create_source,
    reset_tables,
    session_scope,
)
from weather_project.models import DailyWeather
from weather_project.parsers.csv_parser import parse_csv_observations
from weather_project.parsers.pdf_parser import parse_pdf_observation


LOGGER = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    settings = get_settings()

    _extract_pdfs(settings.pdf_zip_path, settings.raw_pdf_dir.parent)
    create_schema(settings.sqlite_path)
    ensure_daily_weather_columns(settings.sqlite_path, _daily_weather_column_types())
    reset_tables(settings.sqlite_path)

    with session_scope(settings.sqlite_path) as session:
        csv_source = get_or_create_source(
            session,
            kind="csv",
            filename=settings.csv_path.name,
            checksum=_sha256(settings.csv_path),
        )
        csv_rows = parse_csv_observations(settings.csv_path)
        for row in csv_rows:
            session.add(
                DailyWeather(
                    observation_date=row.observation_date,
                    source_id=csv_source.id,
                    ingestion_type="csv",
                    temp_max_f=row.temp_max_f,
                    temp_min_f=row.temp_min_f,
                    temp_avg_f=row.temp_avg_f,
                    temp_departure=row.temp_departure,
                    hdd=row.hdd,
                    cdd=row.cdd,
                    precip_inches=row.precip_inches,
                    snow_depth=row.snow_depth,
                    quality_flag=row.quality_flag,
                    parse_notes=row.parse_notes,
                    raw_excerpt=row.raw_excerpt,
                )
            )
        LOGGER.info("Loaded %s CSV observations", len(csv_rows))

        pdf_paths = sorted(
            p for p in settings.raw_pdf_dir.glob("*.pdf") if not p.name.startswith("._")
        )
        pdf_count = 0
        for pdf_path in pdf_paths:
            parsed = parse_pdf_observation(pdf_path)
            if parsed is None:
                LOGGER.warning("Skipping unparseable PDF %s", pdf_path.name)
                continue
            source = get_or_create_source(
                session,
                kind="pdf",
                filename=pdf_path.name,
                checksum=_sha256(pdf_path),
            )
            session.add(
                DailyWeather(
                    observation_date=parsed.observation_date,
                    source_id=source.id,
                    ingestion_type="pdf",
                    temp_max_f=parsed.temp_max_f,
                    temp_min_f=parsed.temp_min_f,
                    temp_avg_f=parsed.temp_avg_f,
                    temp_departure=parsed.temp_departure,
                    hdd=parsed.hdd,
                    cdd=parsed.cdd,
                    precip_inches=parsed.precip_inches,
                    snow_depth=parsed.snow_depth,
                    quality_flag=parsed.quality_flag,
                    parse_notes=parsed.parse_notes,
                    raw_excerpt=parsed.raw_excerpt,
                    **_filter_daily_weather_kwargs(parsed.full_values or {}),
                )
            )
            pdf_count += 1
        LOGGER.info("Loaded %s PDF observations", pdf_count)


def _extract_pdfs(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _filter_daily_weather_kwargs(values: dict[str, object]) -> dict[str, object]:
    allowed = set(DailyWeather.__table__.columns.keys())
    return {key: value for key, value in values.items() if key in allowed}


def _daily_weather_column_types() -> dict[str, str]:
    base = {
        "id",
        "observation_date",
        "source_id",
        "temp_max_f",
        "temp_min_f",
        "temp_avg_f",
        "temp_departure",
        "hdd",
        "cdd",
        "precip_inches",
        "snow_depth",
        "quality_flag",
        "parse_notes",
        "raw_excerpt",
    }
    out: dict[str, str] = {}
    for column in DailyWeather.__table__.columns:
        if column.name in base:
            continue
        if isinstance(column.type, Integer):
            out[column.name] = "INTEGER"
        elif isinstance(column.type, (String, Text)):
            out[column.name] = "TEXT"
        else:
            out[column.name] = "REAL"
    return out


if __name__ == "__main__":
    main()
