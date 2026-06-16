import pandas as pd
import json
import re
from datetime import datetime

with open("config.json") as f:
    config = json.load(f)

COUNTRY_RULES = config["country_phone_rules"]
DATE_FORMATS = config["date_formats"]
CHUNK_SIZE = config["chunk_size"]


def validate_phone(phone, country_code):
    if pd.isna(phone) or str(phone).strip() == "":
        return False, "Missing phone number"
    phone_clean = re.sub(r"[\s\-\+\(\)]", "", str(phone))
    if not phone_clean.isdigit():
        return False, "Phone contains non-numeric characters"
    if country_code not in COUNTRY_RULES:
        return False, f"Unknown country code: {country_code}"
    expected = COUNTRY_RULES[country_code]["digits"]
    if len(phone_clean) != expected:
        return False, f"Phone must be {expected} digits for {country_code}, got {len(phone_clean)}"
    return True, "OK"


def validate_date(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "":
        return False, "Missing date"
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(str(date_val).strip(), fmt)
            return True, "OK"
        except ValueError:
            continue
    return False, f"Date '{date_val}' doesn't match any accepted format"


def validate_row(row, country_code):
    errors = []

    # Phone validation
    phone_ok, phone_msg = validate_phone(row.get("phone_number") or row.get("phone"), country_code)
    if not phone_ok:
        errors.append(phone_msg)

    # Date validation — check any column with 'date' in the name
    for col in row.index:
        if "date" in col.lower() or "time" in col.lower():
            date_ok, date_msg = validate_date(row[col])
            if not date_ok:
                errors.append(f"{col}: {date_msg}")

    # Null checks on critical fields
    critical_fields = ["order_id", "product_id", "payment_mode"]
    for field in critical_fields:
        if field in row.index:
            if pd.isna(row[field]) or str(row[field]).strip() == "":
                errors.append(f"Missing value in '{field}'")

    return errors


def validate_csv(df, country_code):
    df = df.copy()
    df["_errors"] = ""
    df["_status"] = "Valid"

    for idx, row in df.iterrows():
        errors = validate_row(row, country_code)
        if errors:
            df.at[idx, "_errors"] = " | ".join(errors)
            df.at[idx, "_status"] = "Invalid"

    valid_df = df[df["_status"] == "Valid"].drop(columns=["_errors", "_status"])
    invalid_df = df[df["_status"] == "Invalid"]

    summary = {
        "total": len(df),
        "valid": len(valid_df),
        "invalid": len(invalid_df),
        "error_breakdown": {}
    }

    # Count error types
    for err_list in invalid_df["_errors"]:
        for err in err_list.split(" | "):
            key = err.split(":")[0].strip()
            summary["error_breakdown"][key] = summary["error_breakdown"].get(key, 0) + 1

    return valid_df, invalid_df, summary


def split_into_chunks(df, chunk_size=None):
    size = chunk_size or CHUNK_SIZE
    chunks = []
    for i in range(0, len(df), size):
        chunks.append(df.iloc[i:i+size])
    return chunks