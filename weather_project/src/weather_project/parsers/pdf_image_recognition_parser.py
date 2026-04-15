from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from pathlib import Path
from statistics import mean

import pdfplumber

from weather_project.parsers.common import extract_date_from_text

DATE_TEXT_PATTERNS = [
    re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})"),
    re.compile(
        r"([A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
        re.IGNORECASE,
    ),
    re.compile(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", re.IGNORECASE),
]

import shutil


@dataclass
class ParsedImageRecognitionObservation:
    observation_date: date
    values: dict[str, float | None]
    confidence_overall: float | None
    extraction_trace_json: str
    quality_flag: str | None
    parse_notes: str | None
    ocr_raw_excerpt: str


def parse_pdf_image_recognition_observation(pdf_path: Path) -> ParsedImageRecognitionObservation | None:
    ocr_values, ocr_excerpt, trace_json, confidence_overall = _extract_ocr_values_and_trace(pdf_path)
    obs_date = _extract_date(ocr_excerpt)
    if obs_date is None:
        return None

    quality_flag = None
    notes: list[str] = []
    if re.search(r"(?i)\bQC FLAG:\s*0\b", ocr_excerpt):
        quality_flag = "qc_0"
    if re.search(r"(?i)all daily observations\s+MISSING", ocr_excerpt):
        quality_flag = "missing_marked"
        notes.append("daily observations marked missing (M) in source PDF")

    return ParsedImageRecognitionObservation(
        observation_date=obs_date,
        values=ocr_values,
        confidence_overall=confidence_overall,
        extraction_trace_json=trace_json,
        quality_flag=quality_flag,
        parse_notes="; ".join(notes) if notes else None,
        ocr_raw_excerpt="\n".join(ocr_excerpt.splitlines()[:40]),
    )


def infer_dynamic_column_types(values: dict[str, float | None]) -> dict[str, str]:
    return {k: "REAL" for k in values.keys()}


def _extract_ocr_values_and_trace(pdf_path: Path) -> tuple[dict[str, float | None], str, str, float | None]:
    if shutil.which("tesseract") is None:
        raise RuntimeError("tesseract is required for image-recognition ingest")

    ocr_text: list[str] = []
    value_conf: dict[str, tuple[float | None, float]] = {}
    page_traces: list[dict[str, object]] = []
    page_confidences: list[float] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            image = page.to_image(resolution=220).original
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                image.save(tmp_path)
                tsv_text = _run_tesseract_tsv(tmp_path)
                rows = _parse_tsv_rows(tsv_text)
                page_contract = _extract_page_contract(rows, page_idx)
                page_traces.append(page_contract)
                if page_contract["page_confidence"] is not None:
                    page_confidences.append(float(page_contract["page_confidence"]))
                for row in page_contract["rows"]:
                    section = row["section"]
                    metric = row["metric"]
                    line_conf = float(row["line_confidence"])
                    for suffix, val in row["values"].items():
                        key = f"{section}_{metric}_{suffix}"
                        if key not in value_conf or line_conf > value_conf[key][1]:
                            value_conf[key] = (val, line_conf)
                ocr_text.extend(page_contract["line_texts"])
            finally:
                tmp_path.unlink(missing_ok=True)

    values = {k: v for k, (v, _) in value_conf.items()}
    trace_json = json.dumps(
        {
            "engine": "tesseract",
            "mode": "image_first_structured",
            "pages": page_traces,
        }
    )
    overall = mean(page_confidences) if page_confidences else None
    return values, "\n".join(ocr_text), trace_json, overall


def _run_tesseract_tsv(image_path: Path) -> str:
    proc = subprocess.run(
        ["tesseract", str(image_path), "stdout", "--psm", "6", "tsv"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract failed for {image_path.name}: {proc.stderr.strip()}")
    return proc.stdout


def _parse_tsv_rows(tsv_text: str) -> list[dict[str, object]]:
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    rows: list[dict[str, object]] = []
    for row in reader:
        text_val = (row.get("text") or "").strip()
        if not text_val:
            continue
        try:
            conf = float(row.get("conf") or "-1")
        except ValueError:
            conf = -1.0
        if conf < 0:
            continue
        rows.append(
            {
                "block_num": int(row.get("block_num") or 0),
                "par_num": int(row.get("par_num") or 0),
                "line_num": int(row.get("line_num") or 0),
                "left": int(row.get("left") or 0),
                "top": int(row.get("top") or 0),
                "width": int(row.get("width") or 0),
                "height": int(row.get("height") or 0),
                "conf": conf,
                "text": text_val,
            }
        )
    return rows


def _extract_page_contract(rows: list[dict[str, object]], page_number: int) -> dict[str, object]:
    line_map: dict[tuple[int, int, int], list[dict[str, object]]] = {}
    for row in rows:
        key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        line_map.setdefault(key, []).append(row)

    lines: list[dict[str, object]] = []
    for items in line_map.values():
        ordered = sorted(items, key=lambda x: int(x["left"]))
        text = " ".join(str(i["text"]) for i in ordered)
        confs = [float(i["conf"]) for i in ordered]
        lines.append(
            {
                "text": text,
                "items": ordered,
                "line_conf": mean(confs) if confs else 0.0,
            }
        )

    header_line = _find_header_line(lines)
    anchors = _column_anchors(header_line)
    current_section = "daily"
    parsed_rows: list[dict[str, object]] = []
    page_confidences: list[float] = []
    line_texts: list[str] = []

    for line in lines:
        txt = str(line["text"])
        line_texts.append(txt)
        section = _detect_section(txt)
        if section is not None:
            current_section = section

        metric = _detect_metric(txt)
        if metric is None:
            continue

        values = _extract_values_from_line_items(line["items"], anchors)
        if not any(v is not None for v in values.values()):
            continue
        line_conf = float(line["line_conf"])
        page_confidences.append(line_conf)
        parsed_rows.append(
            {
                "section": current_section,
                "metric": metric,
                "values": values,
                "line_confidence": line_conf,
                "line_text": txt,
            }
        )

    return {
        "page_number": page_number,
        "header_detected": header_line["text"] if header_line else None,
        "rows": parsed_rows,
        "line_texts": line_texts,
        "page_confidence": mean(page_confidences) if page_confidences else None,
    }


def _find_header_line(lines: list[dict[str, object]]) -> dict[str, object] | None:
    for line in lines:
        t = str(line["text"]).lower()
        if ("obs" in t or "observed" in t) and "norm" in t and "record" in t:
            return line
    return None


def _column_anchors(header_line: dict[str, object] | None) -> dict[str, float]:
    if header_line is None:
        return {"obs": 250.0, "norm": 350.0, "record_high": 470.0, "record_low": 620.0}
    anchors: dict[str, float] = {}
    for item in header_line["items"]:
        token = str(item["text"]).lower()
        x = float(item["left"]) + float(item["width"]) / 2
        if token in {"obs", "observed"}:
            anchors["obs"] = x
        elif token in {"norm", "normal"}:
            anchors["norm"] = x
        elif token == "high":
            anchors["record_high"] = x
        elif token == "low":
            anchors["record_low"] = x
    defaults = {"obs": 250.0, "norm": 350.0, "record_high": 470.0, "record_low": 620.0}
    for k, v in defaults.items():
        anchors.setdefault(k, v)
    return anchors


def _detect_section(text: str) -> str | None:
    lower = text.lower()
    if "month-to-date" in lower or lower.startswith("mtd"):
        return "mtd"
    if "year-to-date" in lower or lower.startswith("ytd"):
        return "ytd"
    if lower.startswith("daily"):
        return "daily"
    return None


def _detect_metric(text: str) -> str | None:
    lower = text.lower()
    if "avg max" in lower:
        return "avg_max"
    if "avg min" in lower:
        return "avg_min"
    if "snow depth" in lower or re.search(r"\bsnow\b", lower):
        return "snow_depth"
    if "precip" in lower:
        return "precip"
    if "hdd" in lower or "heating degree days" in lower:
        return "hdd"
    if "cdd" in lower or "cooling degree days" in lower:
        return "cdd"
    if "max temp" in lower or re.search(r"\bmax\b", lower):
        return "max_temp"
    if "min temp" in lower or re.search(r"\bmin\b", lower):
        return "min_temp"
    if "avg temp" in lower or re.search(r"\bavg\b", lower):
        return "avg_temp"
    return None


def _extract_values_from_line_items(
    items: list[dict[str, object]], anchors: dict[str, float]
) -> dict[str, float | None]:
    out: dict[str, float | None] = {
        "obs": None,
        "norm": None,
        "record_high": None,
        "record_low": None,
        "record_high_year": None,
        "record_low_year": None,
    }
    years_by_col: dict[str, list[float]] = {"record_high": [], "record_low": []}
    vals_by_col: dict[str, list[float]] = {"obs": [], "norm": [], "record_high": [], "record_low": []}

    for it in items:
        token = str(it["text"])
        num = _parse_numeric_token(token)
        if num is None:
            continue
        x = float(it["left"]) + float(it["width"]) / 2
        col = min(anchors.keys(), key=lambda k: abs(x - anchors[k]))
        if 1000 <= num <= 2100 and col in {"record_high", "record_low"}:
            years_by_col[col].append(num)
        else:
            vals_by_col[col].append(num)

    for col in ("obs", "norm", "record_high", "record_low"):
        if vals_by_col[col]:
            out[col] = vals_by_col[col][0]
    if years_by_col["record_high"]:
        out["record_high_year"] = years_by_col["record_high"][0]
    if years_by_col["record_low"]:
        out["record_low_year"] = years_by_col["record_low"][0]
    return out


def _parse_numeric_token(token: str) -> float | None:
    cleaned = token.strip().replace("—", "").replace("–", "")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_date(full_text: str) -> date | None:
    for pattern in DATE_TEXT_PATTERNS:
        match = pattern.search(full_text)
        if not match:
            continue
        token = match.group(1).replace(".", "")
        token = re.sub(r"(\d)(st|nd|rd|th)", r"\1", token, flags=re.IGNORECASE)
        parsed = extract_date_from_text(token)
        if parsed is not None:
            return parsed
        for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
            try:
                return datetime.strptime(token, fmt).date()
            except ValueError:
                continue
    return None
