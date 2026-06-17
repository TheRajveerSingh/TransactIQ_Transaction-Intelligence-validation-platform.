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


def validate_email(email):
    if pd.isna(email) or str(email).strip() == "":
        return True, "OK"  # email is optional — only validate if present
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, str(email).strip()):
        return False, f"Invalid email format: {email}"
    return True, "OK"


def validate_amount(amount):
    if pd.isna(amount) or str(amount).strip() == "":
        return False, "Missing amount"
    try:
        # Handle international formats: 1.000,50 (European) → 1000.50
        val_str = str(amount).strip()
        # If comma is decimal separator (e.g. 1.234,56)
        if re.match(r'^\d{1,3}(\.\d{3})*(,\d+)?$', val_str):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
        val = float(val_str)
        if val < 0:
            return False, "Amount cannot be negative"
        return True, "OK"
    except ValueError:
        return False, f"Amount '{amount}' is not a valid number"


def validate_row(row, country_code, features, duplicate_ids=None):
    errors = []

    # Phone validation
    if features.get("phone", True):
        phone_col = next((c for c in row.index if "phone" in c.lower()), None)
        if phone_col:
            phone_ok, phone_msg = validate_phone(row[phone_col], country_code)
            if not phone_ok:
                errors.append(phone_msg)

    # Date validation
    if features.get("date", True):
        for col in row.index:
            if "date" in col.lower() or "time" in col.lower():
                date_ok, date_msg = validate_date(row[col])
                if not date_ok:
                    errors.append(f"{col}: {date_msg}")

    # Null checks on critical fields
    if features.get("nulls", True):
        critical_fields = ["order_id", "product_id", "payment_mode"]
        for field in critical_fields:
            if field in row.index:
                if pd.isna(row[field]) or str(row[field]).strip() == "":
                    errors.append(f"Missing value in '{field}'")

    # Amount validation
    if features.get("amount", True):
        amount_col = next((c for c in row.index if "amount" in c.lower() or "price" in c.lower() or "total" in c.lower()), None)
        if amount_col:
            amt_ok, amt_msg = validate_amount(row[amount_col])
            if not amt_ok:
                errors.append(amt_msg)

    # Email validation
    if features.get("email", True):
        email_col = next((c for c in row.index if "email" in c.lower()), None)
        if email_col:
            email_ok, email_msg = validate_email(row[email_col])
            if not email_ok:
                errors.append(email_msg)

    # Duplicate order ID
    if features.get("duplicates", True) and duplicate_ids is not None:
        order_col = next((c for c in row.index if "order_id" in c.lower()), None)
        if order_col and not pd.isna(row[order_col]):
            if row[order_col] in duplicate_ids:
                errors.append(f"Duplicate order_id: {row[order_col]}")

    return errors


def validate_csv(df, country_code, features=None):
    if features is None:
        features = {
            "phone": True, "date": True, "nulls": True,
            "amount": True, "duplicates": True, "email": True
        }

    df = df.copy()
    df["_errors"] = ""
    df["_status"] = "Valid"

    # Find duplicate order IDs upfront
    duplicate_ids = set()
    if features.get("duplicates", True):
        order_col = next((c for c in df.columns if "order_id" in c.lower()), None)
        if order_col:
            counts = df[order_col].value_counts()
            duplicate_ids = set(counts[counts > 1].index)

    for idx, row in df.iterrows():
        errors = validate_row(row, country_code, features, duplicate_ids)
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