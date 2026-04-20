# Banking Fraud Detection — AI Agentic Pipeline

A modern, fast, and local-first AI Banking Fraud Detection system built with **FastAPI**. It showcases a multi-agent approach to transactional fraud detection, complete with local LLM integration (Ollama) and workflow automation (N8N).

## 🚀 Features

- **3-Agent Fraud Pipeline:** 
  - *Agent 1 (Geospatial/Time):* Detects physically impossible travel times between transactions using Haversine formulas.
  - *Agent 2 (Behavioural):* Calculates 90-day historical norms, detects velocity spikes, and monitors high-risk merchant categories (Jewelry, Electronics, etc).
  - *Agent 3 (Aggregator):* Combines signals to produce final `AMAN`, `WARNING`, or `FRAUD` verdicts.
- **AI Chat Assistant:** Local integration with `llama3` via Ollama to natural-language query your transaction history and sales analytics.
- **Bulk Data Import:** Upload custom transaction datasets `.csv` with intelligent validation and automated data-seeding mapping.
- **Webhook Automation:** Endpoints specially formatted for integration with N8N to trigger automated action-flows.
- **Local SQLite DB:** Self-contained, simple architecture — zero configuration required to run.

---

## 🛠️ Project Structure

```text
ai-banking-fraud-demo/
├── main.py                      # Core FastAPI Application
├── documentation.md             # In-depth technical specs & Agent Logic tables
├── requirements.txt             # Python dependencies
├── app/
│   ├── core/
│   │   └── database.py          # SQLite schema & dummy data generation
│   └── services/
│       ├── ai_chat.py           # Ollama / Llama3 connection bridging
│       ├── analytics.py         # Business intelligence queries
│       ├── data_import.py       # Batch CSV Upload handler
│       └── fraud_agents.py      # Core 3-Agent Logic implementation
├── static/                      # Styling & Frontend logical JS
├── templates/                   # Dashboard HTML UI
└── mcp-config/                  # Claude Desktop MCP connection settings
```

---

## 💻 How to Run

### 1. Prerequisites
- **Python 3.10+**
- (Optional) **Ollama** installed and running on your local machine if you want the AI chat functionality active.

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/RusselF/ai-banking-fraud-demo.git
cd ai-banking-fraud-demo

pip install -r requirements.txt
```

### 3. Start the Application
Run the backend web server. The database `.db` and `.json` log files will be generated securely the very first time you boot the app.
```bash
python main.py
```

### 4. Access the Dashboard
Head over to your favorite browser and open:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 📝 Demo Data & CSV Import
The moment you start the app, the SQLite database gracefully supplies itself with over 10 *Dummy Customers*, 20 *Indonesian Cities*, and safely randomized realistic transaction data to simulate an active financial environment.

If you'd like to test your own data:
1. Hit **Download Template** on the dashboard to get the correct layout.
2. Fill your data rows. Note: for the demo, ensure `customer_id` strictly floats from `1-10`.
3. Press **Import CSV** to inject the records securely bypass standard routing.

---

*This project is built as a proof-of-concept exploring deterministic agentic logic fused with LLM insight reasoning frameworks.*
