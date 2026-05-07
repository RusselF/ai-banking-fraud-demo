"""
data_import.py
==============
Service untuk import data transaksi dari file CSV.

Format CSV yang didukung:
    customer_id, amount, city_id, merchant, timestamp
    2, 1500000, 1, Toko Emas Berkah, 2024-05-12 14:30:00

Validasi:
    - customer_id harus 1-10
    - city_id harus 1-20
    - amount harus angka positif
    - timestamp harus format datetime valid
    - merchant tidak boleh kosong
"""

import csv
import io
import sqlite3
from datetime import datetime

DB_PATH = "data/banking.db"

# Batasan data demo
VALID_CUSTOMER_IDS = set(range(1, 11))   # 1-10
VALID_CITY_IDS     = set(range(1, 21))   # 1-20
REQUIRED_COLUMNS   = ["customer_id", "amount", "city_id", "merchant", "timestamp"]


def _get_db() -> sqlite3.Connection:
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_row(row: dict, row_num: int) -> tuple[dict | None, str | None]:
    """Validate a single CSV row.

    Returns:
        (parsed_row, None) if valid
        (None, error_message) if invalid
    """
    # Check required fields exist
    for col in REQUIRED_COLUMNS:
        if col not in row or not str(row[col]).strip():
            return None, f"Row {row_num}: Column '{col}' is empty or not found"

    # Validate customer_id
    try:
        customer_id = int(str(row["customer_id"]).strip())
    except (ValueError, TypeError):
        return None, f"Row {row_num}: customer_id '{row['customer_id']}' is not a valid number"

    if customer_id not in VALID_CUSTOMER_IDS:
        return None, f"Row {row_num}: customer_id {customer_id} is out of range (must be 1-10)"

    # Validate amount
    try:
        amount = float(str(row["amount"]).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None, f"Row {row_num}: amount '{row['amount']}' is not a valid number"

    if amount <= 0:
        return None, f"Row {row_num}: amount must be greater than 0 (found: {amount})"

    # Validate city_id
    try:
        city_id = int(str(row["city_id"]).strip())
    except (ValueError, TypeError):
        return None, f"Row {row_num}: city_id '{row['city_id']}' is not a valid number"

    if city_id not in VALID_CITY_IDS:
        return None, f"Row {row_num}: city_id {city_id} is out of range (must be 1-20)"

    # Validate merchant
    merchant = str(row["merchant"]).strip()
    if len(merchant) < 2:
        return None, f"Row {row_num}: merchant name too short (min 2 characters)"

    # Validate timestamp
    timestamp_str = str(row["timestamp"]).strip()
    try:
        datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            # Try alternative format without seconds
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
            timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try date-only format
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d")
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None, (
                    f"Row {row_num}: timestamp '{timestamp_str}' invalid format. "
                    f"Use: YYYY-MM-DD HH:MM:SS"
                )

    return {
        "customer_id": customer_id,
        "amount":      round(amount, -3),  # Bulatkan ke ribuan terdekat
        "city_id":     city_id,
        "merchant":    merchant,
        "timestamp":   timestamp_str,
        "is_flagged":  0,
    }, None


def import_transactions_from_csv(file_content: str) -> dict:
    """Parse and import transactions from CSV content into the database.

    Args:
        file_content: Raw CSV string with header row.

    Returns:
        Dict with keys:
            success_count: Number of successfully imported rows
            failed_count:  Number of rejected rows
            total_rows:    Total rows processed
            errors:        List of error messages for failed rows
            customers_affected: List of unique customer IDs that received new data
    """
    errors = []
    valid_rows = []

    # Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(file_content))
    except Exception as e:
        return {
            "success_count":      0,
            "failed_count":       0,
            "total_rows":         0,
            "errors":             [f"CSV parsing error: {str(e)}"],
            "customers_affected": [],
        }

    # Validate column headers
    if reader.fieldnames:
        # Strip whitespace from headers
        cleaned_headers = [h.strip().lower() for h in reader.fieldnames]
        missing = [col for col in REQUIRED_COLUMNS if col not in cleaned_headers]
        if missing:
            return {
                "success_count":      0,
                "failed_count":       0,
                "total_rows":         0,
                "errors":             [f"Required columns missing: {', '.join(missing)}"],
                "customers_affected": [],
            }

    # Validate each row
    row_num = 1
    for raw_row in reader:
        row_num += 1
        # Clean whitespace from keys
        row = {k.strip().lower(): v for k, v in raw_row.items()}
        parsed, error = _validate_row(row, row_num)
        if error:
            errors.append(error)
        else:
            valid_rows.append(parsed)

    # Insert valid rows into database
    if valid_rows:
        conn = _get_db()
        cur  = conn.cursor()
        cur.executemany(
            "INSERT INTO transactions "
            "(customer_id, amount, city_id, merchant, timestamp, is_flagged) "
            "VALUES (:customer_id, :amount, :city_id, :merchant, :timestamp, :is_flagged)",
            valid_rows,
        )
        conn.commit()
        conn.close()

    customers_affected = sorted(set(r["customer_id"] for r in valid_rows))

    return {
        "success_count":      len(valid_rows),
        "failed_count":       len(errors),
        "total_rows":         row_num - 1,  # Exclude header
        "errors":             errors,
        "customers_affected": customers_affected,
    }


def generate_csv_template() -> str:
    """Generate a CSV template string with example data for download."""
    lines = [
        "customer_id,amount,city_id,merchant,timestamp",
        "1,500000,1,Convenience Store A,2024-01-15 10:30:00",
        "2,1500000,1,Berkah Gold Shop,2024-01-15 14:00:00",
        "3,250000,3,Convenience Store B,2024-01-16 09:15:00",
    ]
    return "\n".join(lines) + "\n"
