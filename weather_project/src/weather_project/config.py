from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    archive_dir: Path
    pdf_zip_path: Path
    csv_path: Path
    raw_pdf_dir: Path
    sqlite_path: Path


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    archive_dir = project_root.parent / "archive"
    return Settings(
        project_root=project_root,
        archive_dir=archive_dir,
        pdf_zip_path=archive_dir / "weather-pdfs.zip",
        csv_path=archive_dir / "3month_weather.csv",
        raw_pdf_dir=project_root / "data" / "raw" / "weather-pdfs",
        sqlite_path=project_root / "data" / "weather.db",
    )
