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
    image_recognition_observations: Mapped[list[DailyWeatherImageRecognition]] = relationship(  # type: ignore[name-defined]
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
    confidence_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_trace_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="observations")


class DailyWeatherImageRecognition(Base):
    __tablename__ = "daily_weather_image_recognition"
    __table_args__ = (
        UniqueConstraint(
            "observation_date",
            "source_id",
            "ingestion_type",
            name="uq_daily_weather_image_recognition_date_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    ingestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    quality_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # DAILY core weather metrics (initial discovered columns from current 10 PDFs).
    daily_max_temp_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_max_temp_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_max_temp_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_max_temp_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_max_temp_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_max_temp_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_min_temp_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_min_temp_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_min_temp_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_min_temp_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_min_temp_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_min_temp_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_avg_temp_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_avg_temp_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_avg_temp_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_avg_temp_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_avg_temp_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_avg_temp_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_precip_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_precip_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_precip_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_precip_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_precip_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_precip_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_hdd_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_hdd_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_hdd_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_hdd_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_hdd_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_hdd_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_cdd_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_cdd_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_cdd_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_cdd_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_cdd_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_cdd_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    daily_snow_depth_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_snow_depth_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_snow_depth_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_snow_depth_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_snow_depth_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_snow_depth_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    # MTD summary metrics.
    mtd_avg_max_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_max_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_max_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_max_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_max_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_max_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    mtd_avg_min_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_min_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_min_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_min_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_min_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_min_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    mtd_avg_temp_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_temp_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_temp_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_temp_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_temp_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_avg_temp_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    mtd_precip_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_precip_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_precip_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_precip_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_precip_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_precip_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    mtd_hdd_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_hdd_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_hdd_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_hdd_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_hdd_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_hdd_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    mtd_cdd_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_cdd_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_cdd_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_cdd_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_cdd_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtd_cdd_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    # YTD summary metrics.
    ytd_avg_max_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_max_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_max_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_max_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_max_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_max_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_avg_min_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_min_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_min_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_min_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_min_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_min_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_avg_temp_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_temp_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_temp_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_temp_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_temp_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_avg_temp_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_precip_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_precip_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_precip_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_precip_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_precip_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_precip_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_hdd_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_hdd_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_hdd_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_hdd_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_hdd_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_hdd_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_cdd_obs: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_cdd_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_cdd_record_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_cdd_record_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_cdd_record_high_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_cdd_record_low_year: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[Source] = relationship(back_populates="image_recognition_observations")
