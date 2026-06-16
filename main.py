import io
import json
import zipfile
import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from validator import validate_csv, split_into_chunks
from dotenv import load_dotenv
import os
from groq import Groq

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


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
        max_tokens=600
    )

    return response.choices[0].message.content


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
    country_code: str = Form(...),
    chunk_size: int = Form(1000)
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))

        valid_df, invalid_df, summary = validate_csv(df, country_code)

        app.state.valid_df = valid_df
        app.state.invalid_df = invalid_df
        app.state.chunk_size = chunk_size

        invalid_preview = invalid_df.head(50).replace({np.nan: None}).to_dict(orient="records")

        ai_recommendations = get_ai_recommendations(summary["error_breakdown"])

        return JSONResponse({
            "summary": summary,
            "invalid_preview": invalid_preview,
            "columns": list(df.columns),
            "ai_recommendations": ai_recommendations
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/download/valid")
def download_valid():
    df = app.state.valid_df
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=valid_rows.csv"}
    )


@app.get("/download/invalid")
def download_invalid():
    df = app.state.invalid_df
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invalid_rows.csv"}
    )


@app.get("/download/chunks")
def download_chunks():
    df = app.state.valid_df
    chunk_size = app.state.chunk_size
    chunks = split_into_chunks(df, chunk_size)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, chunk in enumerate(chunks):
            csv_data = chunk.to_csv(index=False)
            zf.writestr(f"chunk_{i+1}.csv", csv_data)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=chunks.zip"}
    )