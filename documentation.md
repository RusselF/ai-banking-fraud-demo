# Banking Fraud Detection System
## Technical Documentation v1.0

---

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technical Specification](#technical-specification)
4. [API Documentation](#api-documentation)
5. [Fraud Detection Logic](#fraud-detection-logic)
6. [MCP Integration](#mcp-integration)
7. [N8N Automation](#n8n-automation)
8. [User Manual](#user-manual)
9. [Setup Guide](#setup-guide)
10. [Future Improvements](#future-improvements)

---

## 1. Overview

A fully local, automated banking fraud detection system powered by a 3-agent AI pipeline. The system monitors customer transactions in real-time, detects physically impossible transaction patterns, and generates automated fraud verdicts without any cloud dependency.

**Key Capabilities:**
- Detects geospatially impossible transactions (e.g. Jakarta → Surabaya in 33 minutes)
- Analyses 90-day behavioural patterns per customer
- Generates weighted fraud verdicts: SAFE / WARNING / FRAUD
- Natural language database queries via Claude Desktop (MCP)
- Automated monitoring every 5 minutes via N8N
- Full web dashboard with charts and transaction maps

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                           │
│                                                             │
│   Browser (Web UI)          Claude Desktop (MCP)            │
│   http://localhost:8000     Natural Language Queries        │
└──────────────┬──────────────────────┬───────────────────────┘
               │ HTTP/REST            │ stdio / JSON-RPC 2.0
┌──────────────▼──────────────────────▼───────────────────────┐
│                    FastAPI Backend                           │
│                   (port 8000)                               │
│                                                             │
│  GET  /                         → Web Dashboard             │
│  GET  /api/fraud/{id}           → Run Fraud Analysis        │
│  GET  /api/transactions/{id}    → Customer Transactions     │
│  GET  /api/sales/summary        → Sales Analytics           │
│  GET  /api/customers            → Customer List             │
│  GET  /api/cities               → City Coordinates          │
│  GET  /api/fraud-log            → Fraud Log History         │
│  POST /api/chat                 → AI Chat (Ollama)          │
│  POST /api/webhook/transaction  → Single Transaction Check  │
│  POST /api/webhook/simulate     → Batch All Customers       │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                    SERVICE LAYER                             │
│                                                             │
│  fraud_agents.py    analytics.py    ai_chat.py              │
│  Agent 1,2,3        Sales stats     Ollama integration      │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│                    DATA LAYER                                │
│                                                             │
│  SQLite — data/banking.db                                   │
│  ┌──────────┐ ┌──────────────┐ ┌────────┐ ┌─────────────┐  │
│  │customers │ │ transactions │ │ cities │ │    sales    │  │
│  └──────────┘ └──────────────┘ └────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  AUTOMATION LAYER                            │
│                                                             │
│  N8N (port 5678) — Schedule Trigger every 5 minutes        │
│  → POST /api/webhook/simulate                               │
│  → IF fraud detected → Format report → Log to JSON         │
│  → IF all clear → Log status SAFE                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Technical Specification

### Tech Stack
| Component | Technology | Version |
|-----------|-----------|---------|
| Backend | Python + FastAPI | 3.10 / 0.111 |
| Database | SQLite | 3.x |
| Data Processing | Pandas + NumPy | 2.2 / 1.26 |
| AI/LLM | Ollama + Llama3 | Latest |
| MCP Protocol | MCP SDK | Latest |
| Automation | N8N | Latest |
| Frontend | HTML + CSS + Vanilla JS | — |
| Charts | Chart.js | 4.4.1 |
| Map | Canvas API | Native |

### Database Schema

**customers**
```sql
CREATE TABLE customers (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    salary       TEXT,
    home_city_id INTEGER,
    FOREIGN KEY (home_city_id) REFERENCES cities(id)
);
```

**transactions**
```sql
CREATE TABLE transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    amount      REAL NOT NULL,
    city_id     INTEGER NOT NULL,
    merchant    TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    is_flagged  INTEGER DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (city_id)     REFERENCES cities(id)
);
```

**cities**
```sql
CREATE TABLE cities (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    lat  REAL NOT NULL,
    lon  REAL NOT NULL
);
```

**sales**
```sql
CREATE TABLE sales (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    product   TEXT NOT NULL,
    category  TEXT NOT NULL,
    amount    REAL NOT NULL,
    qty       INTEGER NOT NULL,
    region    TEXT NOT NULL,
    sale_date TEXT NOT NULL
);
```

---

## 4. API Documentation

All endpoints served at `http://localhost:8000`.
Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

### Fraud Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/fraud/{customer_id}` | Run full 3-agent fraud analysis |
| GET | `/api/transactions/{customer_id}` | Get customer transaction history |
| GET | `/api/fraud-log` | Get fraud log history |
| POST | `/api/webhook/transaction` | Analyse single new transaction |
| POST | `/api/webhook/simulate` | Batch analyse all customers |

### Sales Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sales/summary` | Revenue stats, by category, region, monthly trend |

### Utility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers` | List all customers |
| GET | `/api/cities` | List all cities with coordinates |
| POST | `/api/chat` | AI chat with optional fraud/sales context |

---

## 5. Fraud Detection Logic

### Agent 1 — Geospatial & Time Analysis

**Data Preparation:**
```sql
-- Sort by customer + time, get previous transaction using LAG
SELECT
    t.id, t.customer_id, t.amount, t.timestamp, t.merchant,
    c.name AS city, c.lat, c.lon,

    LAG(t.customer_id) OVER (PARTITION BY t.customer_id ORDER BY t.timestamp) AS prev_customer_id,
    LAG(c.lat)         OVER (PARTITION BY t.customer_id ORDER BY t.timestamp) AS prev_lat,
    LAG(c.lon)         OVER (PARTITION BY t.customer_id ORDER BY t.timestamp) AS prev_lon,
    LAG(t.timestamp)   OVER (PARTITION BY t.customer_id ORDER BY t.timestamp) AS prev_timestamp
FROM transactions t
JOIN cities c ON t.city_id = c.id
WHERE t.customer_id = ?
ORDER BY t.customer_id ASC, t.timestamp ASC
```

**Flag Logic:**
```python
# customer_lag = 1 jika transaksi berurutan milik nasabah yang sama
df["customer_lag"] = np.where(df["customer_id"] == df["prev_customer_id"], 1, 0)

# amount_flag = 1 jika nilai transaksi > Rp 5.000.000
df["amount_flag"] = np.where(df["amount"] > 5_000_000, 1, 0)

# Hanya analisa baris dengan customer_lag = 1
df_flagged = df[df["customer_lag"] == 1]
```

**Distance & Time Calculation:**
```python
# Vectorized Haversine formula
distance_km = haversine_vectorized(prev_lat, prev_lon, lat, lon)

# Minimum travel time
if distance_km > 300:
    min_travel = distance_km / 800 + 3   # pesawat + 3 jam bandara
else:
    min_travel = distance_km / 80         # mobil 80 km/h

# Suspicious if arrival faster than physically possible
is_suspicious = (time_diff_hours < min_travel) AND (distance_km > 10)
```

**Risk Scoring:**
```python
base_score   = (min_travel / time_diff).clip(max=90) * 30
amount_bonus = amount_flag * 10   # +10 for high-value transactions
merchant_bonus = 15               # if merchant is jewelry/electronics
final_score  = (base_score + amount_bonus + merchant_bonus).clip(max=100)
```

### Agent 2 — Behavioural Analysis

| Rule | Condition | Score |
|------|-----------|-------|
| Amount spike | Latest txn > 3x average | +40 |
| Frequency spike | This week > 2.5x weekly average | +30 |
| Geographic dispersal | Unique cities > 5 in 90 days | +20 |
| High value count | > 3 transactions above Rp 5jt | +10 |
| Merchant Risk | >= 2 transactions at high-risk merchants | +15 |

### Agent 3 — Verdict Aggregator

```
Combined Score = (Agent1 Score × 0.6) + (Agent2 Score × 0.4)

FRAUD   : Combined Score ≥ 65
WARNING : Combined Score ≥ 35
SAFE    : Combined Score < 35
```

---

## 6. MCP Integration

The system exposes 9 tools to Claude Desktop via MCP (Model Context Protocol) using stdio transport with JSON-RPC 2.0.

**Config location:**
```
Windows: C:\Users\{user}\AppData\Roaming\Claude\claude_desktop_config.json
```

**Config:**
```json
{
  "mcpServers": {
    "banking-fraud": {
      "command": "python",
      "args": ["C:/Users/Russel/ai-demo/mcp_server.py"]
    }
  }
}
```

**Available Tools:**
| Tool | Description |
|------|-------------|
| `get_customers` | List all customers |
| `get_transactions` | Customer transaction history |
| `analyze_location_time` | Agent 1 analysis |
| `analyze_behaviour` | Agent 2 analysis |
| `run_fraud_analysis` | Full 3-agent pipeline |
| `get_sales_summary` | Sales analytics |
| `query_sales` | Filtered sales query |
| `get_cities` | City coordinates |
| `calculate_distance` | Distance between cities |

---

## 7. N8N Automation

**Workflow: Banking Fraud Detection — Auto Monitor**

```
Schedule Trigger (every 5 min)
        ↓
HTTP POST → /api/webhook/simulate
        ↓
Response: { total, fraud, warning, SAFE, results[] }
        ↓
IF json.fraud > 0
        ↓
  TRUE  → Format fraud report → Log to fraud_log.json
  FALSE → Log "semua SAFE" status
```

**Log file:** `data/fraud_log.json`

---

## 8. User Manual

### Running the System

**Terminal 1 — Start FastAPI:**
```bash
cd C:\Users\Russel\ai-demo
python main.py
```

**Terminal 2 — Start N8N:**
```bash
n8n start
```

**Ollama** — Open from Start Menu (runs in background).

### Using the Web Dashboard

Open `http://localhost:8000` in browser.

**Fraud Detection:**
1. Click a customer button (#1 to #10)
2. Click "Jalankan Analisis"
3. View Agent 1, 2, 3 results and final verdict
4. Red highlighted rows = flagged transactions

**Sales Analytics:**
1. Click "Sales Analytics" in sidebar
2. View revenue trend, category breakdown, regional performance, top products

**Transaction Map:**
1. Click "Transaction Map" in sidebar
2. Select a customer to see their transaction locations
3. Red dots = flagged transactions, dashed red line = suspicious pair

**AI Chat:**
1. Click "AI Chat" in sidebar
2. Select mode: General / Fraud Context / Sales Context
3. For Fraud Context, select a customer first
4. Type question in Indonesian or English

### Using Claude Desktop (MCP)

With banking-fraud MCP enabled, ask Claude:
- *"Siapa nasabah paling berisiko fraud hari ini?"*
- *"Analisis semua nasabah dan ranking berdasarkan risk score"*
- *"Berapa jarak Jakarta ke Makassar dan berapa jam perjalanannya?"*
- *"Tampilkan summary penjualan 3 bulan terakhir"*
- *"Customer 7 transaksi di mana saja dalam 90 hari terakhir?"*

---

## 9. Setup Guide

### Prerequisites
- Python 3.10+
- Node.js 20+
- Ollama (https://ollama.ai)
- Claude Desktop (https://claude.ai/download)

### Installation

```bash
# 1. Clone / copy project
cd C:\Users\Russel\ai-demo

# 2. Install Python dependencies
pip install fastapi uvicorn requests pandas numpy mcp python-multipart python-dateutil

# 3. Install N8N
npm install -g n8n

# 4. Pull Ollama model
ollama pull llama3

# 5. Run the app
python main.py
```

### Project Structure
```
ai-demo/
├── main.py                      ← FastAPI entry point
├── mcp_server.py                ← MCP server for Claude Desktop
├── .env                         ← Configuration
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── database.py          ← DB init + dummy data
│   └── services/
│       ├── __init__.py
│       ├── fraud_agents.py      ← Agent 1, 2, 3
│       ├── analytics.py         ← Sales analytics
│       └── ai_chat.py           ← Ollama integration
├── templates/
│   └── index.html               ← Web UI structure
├── static/
│   ├── css/
│   │   └── style.css            ← Styling
│   └── js/
│       └── main.js              ← Frontend logic
├── mcp-config/
│   └── claude_desktop_mcp.json  ← MCP config
├── n8n/
│   └── fraud_workflow.json      ← N8N workflow
└── data/
    ├── banking.db               ← SQLite database
    └── fraud_log.json           ← Fraud detection log
```

---

## 10. Future Improvements

| Priority | Feature | Description |
|----------|---------|-------------|
| ✅ Done | Merchant category flag | Flag transactions at high-risk merchants (electronics, jewelry) |
| ✅ Done | Real CSV import | Upload real customer/transaction data from CSV |
| High | Authentication | API key or JWT auth for endpoints |
| Medium | PostgreSQL migration | Replace SQLite for production scale |
| Medium | Telegram notification | Alert via Telegram bot when FRAUD detected |
| Medium | Real-time dashboard | WebSocket for live fraud log updates |
| Medium | Unit tests | pytest coverage for all agents |
| Low | ML anomaly detection | Isolation Forest / Autoencoder for pattern learning |
| Low | Docker deployment | Containerize for VPS deployment |
| Low | Multi-language support | English UI option |
