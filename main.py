import io
import json
import uuid
import zipfile
import os
import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from validator import validate_csv, split_into_chunks
from dotenv import load_dotenv
from groq import Groq
from fpdf import FPDF

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SESSIONS = {}


def get_ai_recommendations(error_breakdown: dict) -> str:
    if not error_breakdown:
        return "No errors found. Data looks clean!"
    error_summary = "\n".join([f"- {err}: {count} rows" for err, count in error_breakdown.items()])
    prompt = f"""You are a data implementation expert at a CRM company.
A transaction CSV file was validated and the following errors were found:

{error_summary}

For each error type, provide a specific, actionable fix recommendation for the implementation team.
Be concise — one paragraph per error max. Use technical but clear language.
Format your response as:
**[Error Type]**: Your recommendation here.
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800
    )
    return response.choices[0].message.content


def query_dataframe(df: pd.DataFrame, question: str, scope: str) -> dict:
    columns = list(df.columns)
    sample = df.head(3).replace({np.nan: None}).to_dict(orient="records")
    prompt = f"""You are a pandas data analyst. The user has a dataframe with these columns: {columns}
Sample rows: {sample}
Scope: {scope} rows only.

User question: "{question}"

Write a pandas query expression that answers this question.
Respond ONLY with a valid pandas boolean filter expression (no df[], no variable assignment, no explanation).
Example: amount > 5000
Example: customer_name.str.contains('Sharma', case=False)
Example: city == 'Mumbai'
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100
    )
    query_expr = response.choices[0].message.content.strip().strip("`").strip()

    try:
        result = df.query(query_expr)
        return {
            "success": True,
            "query": query_expr,
            "count": len(result),
            "rows": result.replace({np.nan: None}).head(100).to_dict(orient="records"),
            "columns": list(result.columns)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "query": query_expr}


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/config")
def get_config():
    with open("config.json") as f:
        return json.load(f)


@app.post("/validate")
async def validate(
    file: UploadFile = File(...),
    accepted_rules: str = Form("{}"),
    chunk_size: int = Form(1000),
    features: str = Form("{}"),
    date_format: str = Form("ALL")
):
    try:
        features_dict = json.loads(features)
        if not features_dict:
            features_dict = {
                "phone": True, "date": True, "nulls": True,
                "amount": True, "duplicates": True, "email": True
            }

        accepted_rules_dict = json.loads(accepted_rules)
        if not accepted_rules_dict:
            # fallback to IN if nothing selected
            accepted_rules_dict = {"IN": {"name": "India", "digits": 10}}

        try:
            date_fmt_parsed = json.loads(date_format)
            if isinstance(date_fmt_parsed, list) and len(date_fmt_parsed) == 1:
                date_fmt_parsed = date_fmt_parsed[0]
        except (json.JSONDecodeError, TypeError):
            date_fmt_parsed = date_format

        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))

        valid_df, invalid_df, summary = validate_csv(df, accepted_rules_dict, features_dict, date_fmt_parsed)

        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = {
            "valid": valid_df,
            "invalid": invalid_df,
            "full": df
        }

        invalid_preview = invalid_df.head(50).replace({np.nan: None}).to_dict(orient="records")
        valid_preview = valid_df.head(50).replace({np.nan: None}).to_dict(orient="records")

        ai_recommendations = get_ai_recommendations(summary["error_breakdown"])

        return JSONResponse({
            "session_id": session_id,
            "summary": summary,
            "invalid_preview": invalid_preview,
            "valid_preview": valid_preview,
            "columns": list(df.columns),
            "ai_recommendations": ai_recommendations
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/chat")
async def chat(request: dict):
    session_id = request.get("session_id")
    question = request.get("question")
    scope = request.get("scope", "both")

    if not session_id or session_id not in SESSIONS:
        return JSONResponse({"error": "Session not found. Please validate a file first."}, status_code=404)

    session = SESSIONS[session_id]

    if scope == "valid":
        df = session["valid"]
    elif scope == "invalid":
        df = session["invalid"]
    else:
        df = session["full"]

    if df.empty:
        return JSONResponse({"error": "No data available for this scope."}, status_code=400)

    q_lower = question.lower()
    if any(p in q_lower for p in ["how many rows", "total rows", "row count", "how many records", "count of rows"]):
        return JSONResponse({
            "answer": f"There are {len(df)} rows in the {scope} dataset.",
            "has_table": False, "rows": [], "columns": []
        })

    if any(p in q_lower for p in ["how many columns", "column count", "what columns", "list columns", "show columns"]):
        cols = list(df.columns)
        return JSONResponse({
            "answer": f"There are {len(cols)} columns: {', '.join(cols)}.",
            "has_table": False, "rows": [], "columns": []
        })

    result = query_dataframe(df, question, scope)

    if not result["success"]:
        return JSONResponse({
            "answer": f"I couldn't process that query. Try rephrasing it.\n\nError: {result['error']}",
            "has_table": False, "rows": [], "columns": []
        })

    count = result["count"]
    answer = f"Found {count} row{'s' if count != 1 else ''} matching your query."
    if count == 0:
        answer = "No rows matched your query. Try different criteria."

    return JSONResponse({
        "answer": answer,
        "query": result["query"],
        "has_table": count > 0,
        "rows": result.get("rows", []),
        "columns": result.get("columns", [])
    })


@app.get("/download/valid")
def download_valid(session_id: str):
    if session_id not in SESSIONS:
        return JSONResponse({"error": "Session expired"}, status_code=404)
    df = SESSIONS[session_id]["valid"]
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=valid_rows.csv"})


@app.get("/download/invalid")
def download_invalid(session_id: str):
    if session_id not in SESSIONS:
        return JSONResponse({"error": "Session expired"}, status_code=404)
    df = SESSIONS[session_id]["invalid"]
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invalid_rows.csv"})


@app.get("/download/chunks")
def download_chunks(session_id: str, chunk_size: int = 1000):
    if session_id not in SESSIONS:
        return JSONResponse({"error": "Session expired"}, status_code=404)
    df = SESSIONS[session_id]["valid"]
    chunks = split_into_chunks(df, chunk_size)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, chunk in enumerate(chunks):
            zf.writestr(f"chunk_{i+1}.csv", chunk.to_csv(index=False))
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=chunks.zip"})


@app.post("/download/chat-csv")
async def download_chat_csv(request: dict):
    rows = request.get("rows", [])
    columns = request.get("columns", [])
    df = pd.DataFrame(rows, columns=columns)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=query_results.csv"})


@app.post("/download/chat-pdf")
async def download_chat_pdf(request: dict):
    rows = request.get("rows", [])
    columns = request.get("columns", [])
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 8)
    col_width = 190 / max(len(columns), 1)
    for col in columns:
        pdf.cell(col_width, 7, str(col)[:15], border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 7)
    for row in rows[:200]:
        for col in columns:
            val = str(row.get(col, ""))[:15]
            pdf.cell(col_width, 6, val, border=1)
        pdf.ln()
    pdf_bytes = pdf.output()
    return StreamingResponse(iter([bytes(pdf_bytes)]), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=query_results.pdf"})