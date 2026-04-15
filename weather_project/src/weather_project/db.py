from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from weather_project.models import Base, DailyWeather, Source


def get_engine(sqlite_path: Path):
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{sqlite_path}", future=True)


def create_schema(sqlite_path: Path) -> None:
    engine = get_engine(sqlite_path)
    Base.metadata.create_all(engine)


def reset_tables(sqlite_path: Path) -> None:
    engine = get_engine(sqlite_path)
    with Session(engine) as session:
        session.execute(delete(DailyWeather))
        session.execute(delete(Source))
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


def ensure_daily_weather_columns(sqlite_path: Path, column_types: dict[str, str]) -> None:
    """Add missing columns to daily_weather without replacing the table."""
    if not column_types:
        return
    engine = get_engine(sqlite_path)
    with engine.begin() as conn:
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(daily_weather)")).fetchall()
        }
        for column, sql_type in column_types.items():
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE daily_weather ADD COLUMN {column} {sql_type}"))
