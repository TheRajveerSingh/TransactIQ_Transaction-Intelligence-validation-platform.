# TransactIQ

A web-based transaction data validation and processing platform built for implementation teams handling client data onboarding at scale.

## Overview

TransactIQ accepts transaction CSV files containing order-level, product-level, and payment information, performs comprehensive multi-layer validation, and returns cleaned output files ready for system ingestion. Each validation run also generates AI-powered fix recommendations for every error type detected, and an interactive Data Assistant lets teams query their dataset in natural language after validation.

## Features

- **Multi-country phone validation** — each row's `country_code` column is matched against a user-configured list of accepted countries, with per-country digit rules. Adding IN + SG flags US and AE rows even if their digit counts happen to match.
- **Date format validation** — supports DD-MM-YYYY, MM-DD-YYYY, YYYY-MM-DD with separators ( - / . ) accepted in all formats. Users can select one, two, or all formats. Strict calendar validation catches impossible dates like 31st April.
- **Data integrity checks** — null checks on order_id, product_id, and payment_mode
- **Amount validation** — numeric check, negative value detection, international decimal format support (e.g. 1.234,56)
- **Email format validation** — regex-based, optional column
- **Duplicate order ID detection** — flags repeated identifiers across the dataset
- **Configurable validation toggles** — each check can be turned on or off per run
- **Clean and invalid row separation** — download valid rows, invalid rows with error reasons, or valid rows split into chunks as a zip
- **AI-powered fix recommendations** — Groq (LLaMA 3.3 70B) generates actionable fix guidance per error type after each validation run
- **Natural language Data Assistant** — chat interface to query the validated dataset ("show rows where amount > 5000", "find orders from Mumbai"), with table view and CSV/PDF download of results

## Tech Stack

- **Backend:** FastAPI, Python
- **Frontend:** HTML, vanilla JS, custom CSS
- **AI:** Groq API (LLaMA 3.3 70B)
- **Data Processing:** Pandas, NumPy
- **PDF Export:** fpdf2
- **Deployment:** Render

## Setup

1. Clone the repository
2. Create a virtual environment and activate it
3. Install dependencies: `pip install -r requirements.txt`
4. Create a `.env` file with your Groq API key: `GROQ_API_KEY=your_key_here`
5. Run the server: `uvicorn main:app --reload`
6. Open `http://127.0.0.1:8000` in your browser

## Expected CSV Format

| Column | Required | Notes |
|---|---|---|
| order_id | Yes | Checked for nulls and duplicates |
| product_id | Yes | Checked for nulls |
| product_name | No | Informational |
| category | No | Informational |
| customer_name | No | Informational |
| city | No | Informational |
| phone_number | Yes | Validated against country rules |
| country_code | Yes | Matched against accepted countries list |
| payment_mode | Yes | Checked for nulls |
| amount | Yes | Must be numeric and non-negative |
| quantity | No | Informational |
| order_date | Yes | Validated against selected date format |
| email | No | Validated if present |

Date/time columns are auto-detected by column name.

## Configuration

`config.json` defines the base country phone rules and accepted date format variants. Country rules can also be added or removed dynamically from the UI at runtime without restarting the server.

## Tradeoffs

- **Stateless architecture** — no database or user persistence; files and session data are held in memory per server process. On Render's free tier, sessions reset on spin-down.
- **Server-side validation** — runs on the backend to handle large files without browser memory constraints
- **Single-file chunking** — chunks are based on valid rows only; invalid rows are always in a separate file
- **No auth or multi-tenancy** — out of scope for this version; each session is isolated by a UUID

## AI Usage

This project uses Groq (LLaMA 3.3 70B) for two features: generating fix recommendations after validation, and powering the natural language Data Assistant. The assistant converts user questions into pandas query expressions and runs them against the validated dataset in memory.