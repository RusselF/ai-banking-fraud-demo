"""
main.py
=======
FastAPI entry point for the AI Banking & Sales Demo.

Serves:
  - Web dashboard at /
  - Fraud detection API at /api/fraud/
  - Sales analytics API at /api/sales/
  - AI chat API at /api/chat
  - N8N webhook endpoints at /api/webhook/
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from datetime import datetime
import json
import os

from app.core.database import init_db
from app.services.fraud_agents import run_fraud_analysis
from app.services.analytics import get_sales_summary, get_all_transactions, get_cities_map
from app.services.ai_chat import ask_ollama, chat_with_fraud_context, chat_with_sales_context
from app.services.data_import import import_transactions_from_csv, generate_csv_template


# ════════════════════════════════════════════════════════════════
#  APP SETUP
# ════════════════════════════════════════════════════════════════
app = FastAPI(title="AI Banking & Sales Demo", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def startup():
    os.makedirs("data", exist_ok=True)
    init_db()
    print("✅ App started!")


# ════════════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()


# ════════════════════════════════════════════════════════════════
#  FRAUD API
# ════════════════════════════════════════════════════════════════
@app.get("/api/fraud/{customer_id}")
async def fraud_analysis(customer_id: int):
    if customer_id < 1 or customer_id > 10:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    return run_fraud_analysis(customer_id)


@app.get("/api/transactions/{customer_id}")
async def transactions(customer_id: int):
    return get_all_transactions(customer_id)


@app.get("/api/cities")
async def cities():
    return get_cities_map()


# ════════════════════════════════════════════════════════════════
#  SALES API
# ════════════════════════════════════════════════════════════════
@app.get("/api/sales/summary")
async def sales_summary():
    return get_sales_summary()


# ════════════════════════════════════════════════════════════════
#  CSV IMPORT
# ════════════════════════════════════════════════════════════════
@app.post("/api/upload/transactions")
async def upload_transactions(file: UploadFile = File(...)):
    """Upload a CSV file to import transactions into the database."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File harus berformat .csv")

    content = await file.read()

    # Try UTF-8 first, then fallback to latin-1
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    result = import_transactions_from_csv(text)
    return result


@app.get("/api/upload/template")
async def download_csv_template():
    """Download a CSV template with example data."""
    return PlainTextResponse(
        content=generate_csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=template_transaksi.csv"},
    )


# ════════════════════════════════════════════════════════════════
#  CUSTOMERS
# ════════════════════════════════════════════════════════════════
@app.get("/api/customers")
async def customers():
    return [
        {"id": 1,  "name": "Budi Santoso"},
        {"id": 2,  "name": "Siti Rahayu"},
        {"id": 3,  "name": "Agus Permana"},
        {"id": 4,  "name": "Dewi Lestari"},
        {"id": 5,  "name": "Rizky Pratama"},
        {"id": 6,  "name": "Rina Wulandari"},
        {"id": 7,  "name": "Hendra Wijaya"},
        {"id": 8,  "name": "Yanti Kusuma"},
        {"id": 9,  "name": "Doni Setiawan"},
        {"id": 10, "name": "Maya Putri"},
    ]


# ════════════════════════════════════════════════════════════════
#  AI CHAT
# ════════════════════════════════════════════════════════════════
class ChatRequest(BaseModel):
    message: str
    mode: str = "general"    # general | fraud | sales
    context_id: int = None


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.mode == "fraud" and req.context_id:
        fraud_data = run_fraud_analysis(req.context_id)
        response = chat_with_fraud_context(req.message, fraud_data)
    elif req.mode == "sales":
        sales_data = get_sales_summary()
        response = chat_with_sales_context(req.message, sales_data)
    else:
        response = ask_ollama(req.message)
    return {"response": response}


# ════════════════════════════════════════════════════════════════
#  N8N WEBHOOK & FRAUD LOG
# ════════════════════════════════════════════════════════════════
LOG_FILE = "data/fraud_log.json"


class WebhookTransaction(BaseModel):
    customer_id: int
    amount: float
    city: str
    merchant: str


def _read_fraud_log() -> list:
    """Read existing fraud log from disk."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def _write_fraud_log(entry: dict):
    """Append a fraud log entry and keep only the last 100 entries."""
    os.makedirs("data", exist_ok=True)
    logs = _read_fraud_log()
    logs.insert(0, entry)
    logs = logs[:100]
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def _build_log_entry(customer_id: int, result: dict, **extra) -> dict:
    """Build a standardized fraud log entry from analysis result."""
    entry = {
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_id":  customer_id,
        "customer":     result.get("customer_name", "Unknown"),
        "verdict":      result["agent3"]["final_status"],
        "score":        result["agent3"]["combined_score"],
        "action":       result["agent3"]["action"],
        "agent1_score": result["agent1"]["score"],
        "agent2_score": result["agent2"]["score"],
    }
    entry.update(extra)
    return entry


@app.post("/api/webhook/transaction")
async def webhook_transaction(txn: WebhookTransaction):
    """N8N endpoint — analyse a single new transaction and log the result."""
    result    = run_fraud_analysis(txn.customer_id)
    log_entry = _build_log_entry(
        txn.customer_id, result,
        amount=txn.amount, city=txn.city, merchant=txn.merchant,
    )
    _write_fraud_log(log_entry)

    return {
        "status":    "processed",
        "verdict":   log_entry["verdict"],
        "score":     log_entry["score"],
        "action":    log_entry["action"],
        "log_entry": log_entry,
    }


@app.get("/api/fraud-log")
async def get_fraud_log():
    """Return all fraud log entries for the dashboard or N8N."""
    return _read_fraud_log()


@app.post("/api/webhook/simulate")
async def simulate_transactions():
    """Batch analyse all 10 customers at once (used by N8N scheduled trigger)."""
    results = []
    for cid in range(1, 11):
        result    = run_fraud_analysis(cid)
        log_entry = _build_log_entry(cid, result)
        _write_fraud_log(log_entry)
        results.append(log_entry)

    return {
        "total":   len(results),
        "fraud":   sum(1 for r in results if r["verdict"] == "FRAUD"),
        "warning": sum(1 for r in results if r["verdict"] == "WARNING"),
        "aman":    sum(1 for r in results if r["verdict"] == "AMAN"),
        "results": results,
    }


# ════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)