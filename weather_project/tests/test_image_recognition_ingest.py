from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import inspect

from weather_project.db import create_schema, ensure_image_recognition_columns, get_engine
from weather_project.parsers.pdf_image_recognition_parser import (
    infer_dynamic_column_types,
    parse_pdf_image_recognition_observation,
)


def test_parse_each_sample_pdf_for_image_recognition():
    tesseract_available = shutil.which("tesseract") is not None
    if not tesseract_available:
        return
    pdf_dir = Path(__file__).resolve().parents[1] / "data" / "raw" / "weather-pdfs"
    filenames = [
        "weather_mar09.pdf",
        "weather_mar10.pdf",
        "weather_mar11.pdf",
        "weather_mar12.pdf",
        "weather_mar13.pdf",
        "weather_mar14.pdf",
        "weather_mar15.pdf",
        "weather_mar16.pdf",
        "weather_mar17.pdf",
        "weather_mar18.pdf",
    ]
    for filename in filenames:
        path = pdf_dir / filename
        if not path.exists():
            continue
        obs = parse_pdf_image_recognition_observation(path)
        assert obs is not None
        assert obs.observation_date is not None
        assert obs.extraction_trace_json
        assert obs.confidence_overall is None or obs.confidence_overall >= 0
        if filename == "weather_mar18.pdf":
            assert obs.quality_flag == "missing_marked"
            assert obs.values.get("daily_max_temp_obs") is None


def test_infer_dynamic_columns_and_schema_evolution(tmp_path: Path):
    db_path = tmp_path / "weather_test.db"
    create_schema(db_path)

    inferred = infer_dynamic_column_types(
        {
            "daily_max_temp_obs": 70.0,
            "new_metric_from_future_ingest": 12.0,
        }
    )
    ensure_image_recognition_columns(db_path, inferred)

    inspector = inspect(get_engine(db_path))
    cols = {c["name"] for c in inspector.get_columns("daily_weather_image_recognition")}
    assert "daily_max_temp_obs" in cols
    assert "new_metric_from_future_ingest" in cols
