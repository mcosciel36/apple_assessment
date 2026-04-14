from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    observations: Mapped[list[DailyWeather]] = relationship(  # type: ignore[name-defined]
        back_populates="source", cascade="all, delete-orphan"
    )


class DailyWeather(Base):
    __tablename__ = "daily_weather"
    __table_args__ = (
        UniqueConstraint("observation_date", "source_id", name="uq_daily_weather_date_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)

    temp_max_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_min_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_avg_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_departure: Mapped[float | None] = mapped_column(Float, nullable=True)
    hdd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cdd: Mapped[float | None] = mapped_column(Float, nullable=True)
    precip_inches: Mapped[float | None] = mapped_column(Float, nullable=True)
    snow_depth: Mapped[float | None] = mapped_column(Float, nullable=True)

    quality_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="observations")
