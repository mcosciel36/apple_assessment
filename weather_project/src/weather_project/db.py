from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from weather_project.models import Base, DailyWeather, DailyWeatherImageRecognition, Source


def get_engine(sqlite_path: Path):
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{sqlite_path}", future=True)


def create_schema(sqlite_path: Path) -> None:
    engine = get_engine(sqlite_path)
    Base.metadata.create_all(engine)


def reset_tables(sqlite_path: Path) -> None:
    engine = get_engine(sqlite_path)
    with Session(engine) as session:
        session.execute(delete(DailyWeatherImageRecognition))
        session.execute(delete(DailyWeather))
        session.execute(delete(Source))
        session.commit()


def reset_image_recognition_table(sqlite_path: Path) -> None:
    """Clear only image-recognition rows, keeping existing ingest outputs intact."""
    engine = get_engine(sqlite_path)
    with Session(engine) as session:
        session.execute(delete(DailyWeatherImageRecognition))
        session.commit()


@contextmanager
def session_scope(sqlite_path: Path) -> Iterator[Session]:
    engine = get_engine(sqlite_path)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_or_create_source(
    session: Session, *, kind: str, filename: str, checksum: str | None
) -> Source:
    existing = session.execute(select(Source).where(Source.filename == filename)).scalar_one_or_none()
    if existing is not None:
        existing.kind = kind
        existing.checksum = checksum
        existing.ingested_at = datetime.now(timezone.utc)
        return existing

    source = Source(
        kind=kind,
        filename=filename,
        checksum=checksum,
        ingested_at=datetime.now(timezone.utc),
    )
    session.add(source)
    session.flush()
    return source


def ensure_image_recognition_columns(sqlite_path: Path, columns: dict[str, str]) -> None:
    """
    Add missing columns to daily_weather_image_recognition additively.

    Parameters
    ----------
    sqlite_path:
        SQLite database path.
    columns:
        Mapping of column_name -> SQLite type (e.g. REAL, TEXT).
    """
    if not columns:
        return
    engine = get_engine(sqlite_path)
    inspector = inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns("daily_weather_image_recognition")}
    safe_type_map = {"REAL", "TEXT", "INTEGER"}

    with engine.begin() as conn:
        for col, col_type in columns.items():
            if col in existing_cols:
                continue
            normalized_type = col_type.upper().strip()
            if normalized_type not in safe_type_map:
                raise ValueError(f"Unsupported SQLite type for dynamic column {col}: {col_type}")
            conn.execute(
                text(f"ALTER TABLE daily_weather_image_recognition ADD COLUMN {col} {normalized_type}")
            )
