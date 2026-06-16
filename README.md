# TransactIQ

A web-based transaction data validation and processing platform built for implementation teams handling client data onboarding.

## Overview

TransactIQ accepts transaction CSV files containing order-level, product-level, and payment information, performs comprehensive validation, and returns cleaned output files ready for system ingestion. It also provides AI-powered fix recommendations for every error type detected.

## Features

- Phone number validation driven by configurable country-specific rules
- Date and time format validation against multiple accepted formats
- Data integrity checks across critical fields (order ID, product ID, payment mode)
- Clean and invalid row separation with individual download options
- Automatic chunking of large CSV files into manageable pieces
- AI-powered fix recommendations for each error category via Groq (LLaMA 3.3)
- Config-driven country code rules extensible from the UI at runtime

## Tech Stack

- Backend: FastAPI, Python
- Frontend: HTML, Tailwind CSS
- AI: Groq API (LLaMA 3.3 70B)
- Data Processing: Pandas, NumPy

## Setup

1. Clone the repository
2. Create a virtual environment and activate it
3. Install dependencies: `pip install -r requirements.txt`
4. Create a `.env` file with your Groq API key: `GROQ_API_KEY=your_key_here`
5. Run the server: `uvicorn main:app --reload`
6. Open `http://127.0.0.1:8000` in your browser

## CSV Format

The platform expects a CSV file with the following columns:

- order_id
- product_id
- phone_number
- payment_mode
- Any date/time columns (auto-detected by column name)

## Configuration

Country phone rules are defined in `config.json` and can also be added dynamically from the UI without restarting the server.

## Tradeoffs

- Stateless architecture: no database or user persistence, files are processed in memory
- Validation runs server-side to handle large files without browser memory constraints
- Auth and multi-tenancy were out of scope for this version