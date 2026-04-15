# Screenshot (image) vs parsed database validation

This document tells **you** and **coding assistants / LLMs** how to reconcile what appears on the March daily **screenshots** under `data/raw/daily_images/` with what landed in **`data/weather.db`** from PDF ingestion—without relying on OCR engines such as Tesseract.

## Why this exists

- PDFs vary by day; the parser fills `daily_*`, `mtd_*`, and `ytd_*` columns when the layout allows.
- Screenshots are the human “ground truth” for what the report *looked like* when captured.
- An LLM with **image input** (or an editor that sends image pixels to the model) can read values off the PNGs directly; do **not** assume OCR on noisy desktop screenshots.

## Preconditions

1. Run ingest from `weather_project/` so SQLite is current:

   `poetry run ingest-weather`  
   (equivalent: `poetry run python -m weather_project.ingest`)

2. Confirm paths (adjust if your clone lives elsewhere):

   - Database: `weather_project/data/weather.db`
   - Images: `weather_project/data/raw/daily_images/march_9.png` … `march_18.png`
   - PDFs (optional cross-check): `weather_project/data/raw/weather-pdfs/weather_mar09.pdf` … `weather_mar18.pdf`

3. Map filename → date:

   - `march_9.png` → `2026-03-09`
   - `march_18.png` → `2026-03-18`

## What to compare (PDF row in SQLite)

Query **only PDF-sourced rows** (`ingestion_type = 'pdf'`) for the March window you have images for:

```sql
SELECT d.observation_date, s.filename,
       d.quality_flag,
       d.temp_max_f, d.temp_min_f, d.temp_avg_f, d.precip_inches, d.hdd, d.cdd,
       d.daily_temp_max_obs, d.daily_temp_max_norm,
       d.daily_temp_min_obs, d.daily_temp_min_norm,
       d.daily_temp_avg_obs, d.daily_temp_avg_norm,
       d.daily_precip_inches_obs, d.daily_precip_inches_norm,
       d.daily_hdd_obs, d.daily_hdd_norm, d.daily_cdd_obs, d.daily_cdd_norm,
       d.daily_temp_max_record_high, d.daily_temp_max_record_high_year,
       d.daily_temp_max_record_low, d.daily_temp_max_record_low_year,
       d.mtd_avg_max_f_obs, d.mtd_avg_max_f_norm,
       d.mtd_avg_min_f_obs, d.mtd_avg_min_f_norm,
       d.mtd_precip_inches_obs, d.mtd_precip_inches_norm,
       d.mtd_cdd_obs, d.mtd_cdd_norm,
       d.ytd_precip_inches_obs, d.ytd_hdd_obs, d.ytd_cdd_obs, d.ytd_temp_avg_obs
FROM daily_weather d
JOIN sources s ON s.id = d.source_id
WHERE s.kind = 'pdf'
  AND d.observation_date BETWEEN '2026-03-09' AND '2026-03-18'
ORDER BY d.observation_date;
```

### Reading order on the image vs columns

- **Daily table** “Observed / Normal” → `daily_*_obs` / `daily_*_norm` (temps, precip, HDD, CDD).
- **Record** columns on the same metric → `daily_*_record_high` (+ `_year`), `daily_*_record_low` (+ `_year`) where present.
- **MTD** block → `mtd_*` columns (not every PDF has every MTD field).
- **YTD** prose/footer (e.g. “YTD Statistics … Precip 6.72 in”) → `ytd_*`, **not** `daily_precip_inches_obs`.
- **All daily observed marked `M`** (e.g. March 18 note) → expect `quality_flag = missing_marked`, null legacy daily obs, norms still populated; YTD totals may still appear in `ytd_*`.

## Procedure (for a human or LLM)

1. Open or attach **`march_N.png`** for the day under test.
2. Read numbers **from the image** (Observed, Normal, MTD/YTD as applicable). Ignore macOS chrome unless it obscures the PDF.
3. Run the SQL above (or a narrowed `WHERE d.observation_date = '2026-03-13'`) and locate that date’s row.
4. For each visible field, check equality (allow small float tolerance for decimals, e.g. `0.01`).
5. Record **pass/fail** and the exact **field name** + **image value** + **DB value** when they differ.

## Pitfalls (call these out in a review)

| Topic | Guidance |
|--------|------------|
| **YTD vs daily precip** | A large “precip” number in **footer YTD** belongs in `ytd_precip_inches_obs`, not `daily_precip_inches_obs`, when daily obs is `M` or `0.00`. |
| **Screenshots** | Some PNGs include Preview UI or stacked windows; read the **foreground** PDF page titled `weather_marNN.pdf`. |
| **No OCR** | Do not ask the model to run Tesseract; use image understanding or human eyes. |
| **Sparse layouts** | If the image has no “Normal” for a metric, `NULL` in DB for that `daily_*_norm` can be correct. |

## Automation in-repo

- **`notebooks/weather_analysis_full_columns.ipynb`** — `image_truth` dict + `parse_gap_summary`: compares a **curated** subset of fields to the DB; empty table means those fields match after ingest.
- **`scripts/report_pdf_ingest_vs_images.sh`** — SQL dump of PDF rows + filename token match to `daily_images` (sanity, not pixel-level proof).

## Copy-paste prompt (for Cursor / other LLMs)

Use this after ingest. Attach the `march_*.png` files or ensure they live under the workspace so the tool can open them. Reference this file with `@docs/llm_image_db_validation.md` from `weather_project/`.

```text
You are helping validate weather PDF ingestion.

Rules:
- Do NOT use Tesseract or other OCR pipelines. Read values from the provided PNG screenshots (image input / workspace images) or describe what you see.
- Ground database: weather_project/data/weather.db (table daily_weather, join sources where kind='pdf', ingestion_type='pdf').
- Ground images: weather_project/data/raw/daily_images/march_9.png through march_18.png (march_K → 2026-03-K).
- Compare visible Observed/Normal/MTD/YTD on each image to the SQLite row for that observation_date. Use the column mapping in docs/llm_image_db_validation.md.
- Flag YTD precip shown in footer vs daily precip obs. Flag missing_marked days (all daily M) vs numeric YTD fields.
- Output a compact markdown table: date | field | image | db | match?

Follow the project doc: weather_project/docs/llm_image_db_validation.md
```

---

Keeping this file up to date when the March image set or schema changes is enough; extend the SQL column list if new `daily_*` / `mtd_*` / `ytd_*` fields are added.
