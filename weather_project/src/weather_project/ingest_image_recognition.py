from __future__ import annotations

import hashlib
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from weather_project.config import get_settings
from weather_project.db import (
    create_schema,
    ensure_image_recognition_columns,
    get_or_create_source,
    reset_image_recognition_table,
    session_scope,
)
from weather_project.parsers.pdf_image_recognition_parser import (
    infer_dynamic_column_types,
    parse_pdf_image_recognition_observation,
)

LOGGER = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    settings = get_settings()

    _extract_pdfs(settings.pdf_zip_path, settings.raw_pdf_dir.parent)
    create_schema(settings.sqlite_path)
    reset_image_recognition_table(settings.sqlite_path)

    pdf_paths = sorted(
        p for p in settings.raw_pdf_dir.glob("*.pdf") if not p.name.startswith("._")
    )
    parsed_map: dict[Path, object] = {}
    dynamic_types: dict[str, str] = {
        "confidence_overall": "REAL",
        "extraction_trace_json": "TEXT",
        "ocr_raw_excerpt": "TEXT",
        "raw_excerpt": "TEXT",
        "parse_notes": "TEXT",
        "quality_flag": "TEXT",
    }
    skipped = 0
    for pdf_path in pdf_paths:
        parsed = parse_pdf_image_recognition_observation(pdf_path)
        if parsed is None:
            skipped += 1
            LOGGER.warning("Skipping unparseable PDF %s", pdf_path.name)
            continue
        parsed_map[pdf_path] = parsed
        dynamic_types.update(infer_dynamic_column_types(parsed.values))

    ensure_image_recognition_columns(settings.sqlite_path, dynamic_types)

    inserted = 0
    with session_scope(settings.sqlite_path) as session:
        for pdf_path in pdf_paths:
            parsed = parsed_map.get(pdf_path)
            if parsed is None:
                continue
            source = get_or_create_source(
                session,
                kind="pdf",
                filename=pdf_path.name,
                checksum=_sha256(pdf_path),
            )
            row = {
                "observation_date": parsed.observation_date.isoformat(),
                "source_id": source.id,
                "ingestion_type": "image_rec",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "quality_flag": parsed.quality_flag,
                "parse_notes": parsed.parse_notes,
                "confidence_overall": parsed.confidence_overall,
                "extraction_trace_json": parsed.extraction_trace_json,
                "raw_excerpt": parsed.ocr_raw_excerpt,
                "ocr_raw_excerpt": parsed.ocr_raw_excerpt,
            }
            row.update(parsed.values)
            _insert_dynamic_row(session, row)
            inserted += 1
    LOGGER.info(
        "Loaded %s image-recognition observations from PDFs (%s skipped)", inserted, skipped
    )


def _insert_dynamic_row(session, row: dict[str, object]) -> None:
    columns = list(row.keys())
    placeholders = [f":{c}" for c in columns]
    sql = text(
        "INSERT INTO daily_weather_image_recognition "
        f"({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
    )
    session.execute(sql, row)


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


if __name__ == "__main__":
    main()
