# Weather Data Project

Your goal is to help stakeholders understand past weather in Downtown LA.

---

## Dataset Overview

The `weather-pdfs` folder contains 10 PDFs, one per day of weather. Note that each PDF may be formatted differently and data may be inconsistent across files.

The `3month_weather.csv` contains the past 3 months of weather data for longer term analysis. Note that the CSV is poorly formatted.

You can choose to utilize one or both in your analysis. Do note that the data from the past 10 days may or may not match the data from the past 3 months.

## Phase 1 — Data Ingestion & Storage

Parse all 10 PDFs and load the data into a structured database of your choice. We care less about parsing accuracy and more about clean pipeline design — your goal is to clearly explain your methodology, how you handled the challenges of parsing, and how your pipeline is structured for modularity and reuse.

- Extract data programmatically — not manually
- Design a schema that could scale to more files
- Write a repeatable ingestion script
- Handle missing or inconsistent fields gracefully
- Document schema decisions and assumptions

Feel free to include a Jupyter Notebook of approaches you tried but didn't make the final cut.

---

## Phase 2 — Data Analysis

Surface insights using a Jupyter Notebook (pandas, matplotlib, seaborn, etc.) or Tableau — your choice. Present your findings as a meaningful data story, not just a collection of charts.

- At least 3 distinct analyses or charts
- Data sourced from your database — not hardcoded
- Label axes, units, and sources clearly
- Brief written explanation per analysis

---

## What to Submit

1. Code repo of your data ingestion pipeline
2. Database schema overview
3. Jupyter Notebook or Tableau workbook of your data analysis
4. Chatbot demo recording

---

## What to Expect

You are expected to submit your project at least 48 hours in advance of our target review date. In the review meeting, we will discuss your project deliverables and your background.

Have fun! ☀️
