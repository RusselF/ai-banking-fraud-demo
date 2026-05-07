"""
fraud_agents.py
===============
Banking Fraud Detection — 3 Agent Pipeline

Agent 1 : Geospatial & Time Analysis
          Detects physically impossible transactions using
          Haversine distance and minimum travel time calculation.

Agent 2 : Behavioural Analysis (90-day window)
          Analyses spending patterns, frequency spikes,
          geographic dispersal, and high-risk merchant activity.

Agent 3 : Verdict Aggregator
          Weighted combined score (60% Agent1 + 40% Agent2)
          Thresholds: FRAUD >= 65 | WARNING >= 35 | AMAN < 35
"""

import sqlite3
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ════════════════════════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("fraud_agents")


# ════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════════
DB_PATH = "data/banking.db"

# Fraud scoring thresholds
FRAUD_SCORE_THRESHOLD   = 65
WARNING_SCORE_THRESHOLD = 35

# Transaction amount threshold (Rp 5.000.000)
HIGH_VALUE_THRESHOLD = 5_000_000

# Travel speed assumptions for impossible-travel detection
FLIGHT_SPEED_KMH    = 800
CAR_SPEED_KMH       = 80
FLIGHT_THRESHOLD_KM = 300   # Jarak > ini = asumsi pesawat
AIRPORT_OVERHEAD_H  = 3     # Waktu tambahan bandara
MIN_SUSPICIOUS_KM   = 10    # Jarak minimum untuk dianggap berpindah kota

# Customer name lookup
CUSTOMERS_MAP = {
    1: "Budi Santoso",   2: "Siti Rahayu",    3: "Agus Permana",
    4: "Dewi Lestari",   5: "Rizky Pratama",   6: "Rina Wulandari",
    7: "Hendra Wijaya",  8: "Yanti Kusuma",    9: "Doni Setiawan",
    10: "Maya Putri",
}


# ════════════════════════════════════════════════════════════════
#  MERCHANT RISK CLASSIFICATION
# ════════════════════════════════════════════════════════════════
MERCHANT_RISK_CATEGORIES = {
    "electronics": {
        "keywords":   ["elektronik", "hp ", "samsung", "laptop", "komputer", "ipad", "apple"],
        "risk_bonus": 15,
        "label":      "Electronics (High Risk)",
        "level":      "high",
    },
    "jewelry": {
        "keywords":   ["emas", "perhiasan", "jewelry", "berlian", "mulia"],
        "risk_bonus": 15,
        "label":      "Jewelry (High Risk)",
        "level":      "high",
    },
    "cash_withdrawal": {
        "keywords":   ["atm", "transfer", "tarik tunai", "setor tunai"],
        "risk_bonus": 10,
        "label":      "Cash Withdrawal",
        "level":      "medium",
    },
    "travel": {
        "keywords":   ["garuda", "lion air", "hotel", "tiket", "sriwijaya"],
        "risk_bonus": 5,
        "label":      "Travel",
        "level":      "low",
    },
}


def classify_merchant_risk(merchant_name: str) -> dict | None:
    """Classify a merchant name into a risk category.

    Args:
        merchant_name: Name of the merchant (e.g. "Toko Emas Berkah")

    Returns:
        Dict with keys {category, label, risk_bonus, level} or None if normal.
    """
    if not merchant_name:
        return None
    name_lower = merchant_name.lower()
    for cat_key, cat_info in MERCHANT_RISK_CATEGORIES.items():
        for keyword in cat_info["keywords"]:
            if keyword in name_lower:
                return {
                    "category":   cat_key,
                    "label":      cat_info["label"],
                    "risk_bonus": cat_info["risk_bonus"],
                    "level":      cat_info["level"],
                }
    return None


# ════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════
def get_db() -> sqlite3.Connection:
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def haversine_vectorized(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vectorized Haversine formula — distance (km) for entire arrays at once."""
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1))
        * np.cos(np.radians(lat2))
        * np.sin(dlon / 2) ** 2
    )
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def calc_min_travel_hours(distance_km: float) -> float:
    """Minimum realistic travel time based on distance."""
    if distance_km > FLIGHT_THRESHOLD_KM:
        return distance_km / FLIGHT_SPEED_KMH + AIRPORT_OVERHEAD_H
    return distance_km / CAR_SPEED_KMH


def _score_to_status(score: float) -> str:
    """Convert a numeric risk score to a status label."""
    if score >= FRAUD_SCORE_THRESHOLD:
        return "FRAUD"
    if score >= WARNING_SCORE_THRESHOLD:
        return "WARNING"
    return "SAFE"


def _empty_agent1_result(reason: str) -> dict:
    """Return a safe default result when Agent 1 has no data to analyse."""
    return {
        "agent":   "Agent 1 — Geospatial & Time Analysis",
        "status":  "SAFE",
        "score":   0,
        "details": [],
        "summary": {},
        "reason":  reason,
    }


# ════════════════════════════════════════════════════════════════
#  AGENT 1 — Geospatial & Time Analysis
# ════════════════════════════════════════════════════════════════
def agent_1_location_time(customer_id: int) -> dict:
    """Detect physically impossible transactions.

    Pipeline:
        1. Query transactions with LAG window (previous txn per customer)
        2. Flag consecutive pairs (customer_lag) and high-value amounts
        3. Compute Haversine distance & time difference (vectorized)
        4. Mark suspicious pairs (arrived faster than physically possible)
        5. Classify merchant risk and compute final score with bonuses
    """
    logger.info(f"Agent 1 — analysing customer_id={customer_id}")
    conn = get_db()

    # Step 1: Query with LAG window functions
    query = """
        SELECT
            t.id, t.customer_id, t.amount, t.timestamp, t.merchant,
            c.name AS city, c.lat, c.lon,

            LAG(t.customer_id) OVER w AS prev_customer_id,
            LAG(c.name)        OVER w AS prev_city,
            LAG(c.lat)         OVER w AS prev_lat,
            LAG(c.lon)         OVER w AS prev_lon,
            LAG(t.timestamp)   OVER w AS prev_timestamp,
            LAG(t.merchant)    OVER w AS prev_merchant,
            LAG(t.amount)      OVER w AS prev_amount,
            LAG(t.id)          OVER w AS prev_id

        FROM transactions t
        JOIN cities c ON t.city_id = c.id
        WHERE t.customer_id = ?
        WINDOW w AS (PARTITION BY t.customer_id ORDER BY t.timestamp)
        ORDER BY t.timestamp ASC
    """
    df = pd.read_sql_query(query, conn, params=(customer_id,))
    conn.close()

    if df.empty:
        return _empty_agent1_result("Transaction data not found")

    # Step 2: Flag consecutive pairs & high-value
    df["customer_lag"] = np.where(df["customer_id"] == df["prev_customer_id"], 1, 0)
    df["amount_flag"]  = np.where(df["amount"] > HIGH_VALUE_THRESHOLD, 1, 0)

    df_pairs = df[df["customer_lag"] == 1].copy()
    if df_pairs.empty:
        return _empty_agent1_result("No transaction pairs available to compare")

    # Step 3: Distance & time calculation (vectorized)
    df_pairs["timestamp"]      = pd.to_datetime(df_pairs["timestamp"])
    df_pairs["prev_timestamp"] = pd.to_datetime(df_pairs["prev_timestamp"])

    df_pairs["time_diff_hours"] = (
        (df_pairs["timestamp"] - df_pairs["prev_timestamp"]).dt.total_seconds() / 3600
    ).abs()

    df_pairs["distance_km"] = haversine_vectorized(
        df_pairs["prev_lat"].values, df_pairs["prev_lon"].values,
        df_pairs["lat"].values,      df_pairs["lon"].values,
    )
    df_pairs["min_travel_hours"] = df_pairs["distance_km"].apply(calc_min_travel_hours)

    # Step 4: Suspicious detection
    df_pairs["is_suspicious"] = (
        (df_pairs["time_diff_hours"] < df_pairs["min_travel_hours"])
        & (df_pairs["distance_km"] > MIN_SUSPICIOUS_KM)
    )

    # Step 5: Merchant risk classification
    df_pairs["merchant_risk"]       = df_pairs["merchant"].apply(classify_merchant_risk)
    df_pairs["merchant_risk_bonus"] = df_pairs["merchant_risk"].apply(
        lambda r: r["risk_bonus"] if r else 0
    )

    # Step 6: Risk score = base + amount_bonus + merchant_bonus
    df_pairs["score"] = 0
    suspicious_mask = df_pairs["is_suspicious"]

    if suspicious_mask.any():
        base_score = (
            (df_pairs.loc[suspicious_mask, "min_travel_hours"]
             / df_pairs.loc[suspicious_mask, "time_diff_hours"].clip(lower=0.01))
            * 30
        ).clip(upper=90)

        amount_bonus   = df_pairs.loc[suspicious_mask, "amount_flag"] * 10
        merchant_bonus = df_pairs.loc[suspicious_mask, "merchant_risk_bonus"]

        df_pairs.loc[suspicious_mask, "score"] = (
            base_score + amount_bonus + merchant_bonus
        ).clip(upper=100).astype(int)

    # Build output
    recent_pairs = df_pairs.tail(10)
    pairs_output = []

    for _, row in recent_pairs.iterrows():
        mr = row["merchant_risk"]
        pairs_output.append({
            "txn_current": {
                "id":                  int(row["id"]),
                "city":                row["city"],
                "time":                str(row["timestamp"]),
                "merchant":            row["merchant"],
                "amount":              row["amount"],
                "amount_flag":         int(row["amount_flag"]),
                "merchant_category":   mr["category"] if mr else None,
                "merchant_risk_label": mr["label"]    if mr else None,
                "merchant_risk_level": mr["level"]    if mr else None,
            },
            "txn_previous": {
                "id":       int(row["prev_id"]) if pd.notna(row["prev_id"]) else None,
                "city":     row["prev_city"],
                "time":     str(row["prev_timestamp"]),
                "merchant": row["prev_merchant"],
                "amount":   row["prev_amount"],
            },
            "distance_km":      round(float(row["distance_km"]), 1),
            "time_diff_hours":  round(float(row["time_diff_hours"]), 2),
            "min_travel_hours": round(float(row["min_travel_hours"]), 2),
            "customer_lag":     int(row["customer_lag"]),
            "is_suspicious":    bool(row["is_suspicious"]),
            "score":            int(row["score"]),
        })

    # Summary stats
    max_score        = int(df_pairs["score"].max())
    n_suspicious     = int(df_pairs["is_suspicious"].sum())
    n_high_value     = int(df_pairs["amount_flag"].sum())
    n_risky_merchant = int((df_pairs["merchant_risk_bonus"] > 0).sum())
    n_total_pairs    = len(df_pairs)
    status           = _score_to_status(max_score)

    logger.info(
        f"Agent 1 done — status={status} score={max_score} "
        f"suspicious={n_suspicious}/{n_total_pairs} risky_merchants={n_risky_merchant}"
    )

    return {
        "agent":   "Agent 1 — Geospatial & Time Analysis",
        "status":  status,
        "score":   max_score,
        "details": pairs_output,
        "summary": {
            "total_pairs_analysed": n_total_pairs,
            "suspicious_pairs":     n_suspicious,
            "high_value_flagged":   n_high_value,
            "risky_merchant_count": n_risky_merchant,
            "high_value_threshold": f"Rp {HIGH_VALUE_THRESHOLD:,}",
        },
        "reason": (
            f"{n_suspicious} suspicious pairs from {n_total_pairs} analysed "
            f"(customer_lag=1). {n_high_value} high-value, "
            f"{n_risky_merchant} risky-merchant transactions flagged."
        ),
    }


# ════════════════════════════════════════════════════════════════
#  AGENT 2 — Behavioural Analysis
# ════════════════════════════════════════════════════════════════
def agent_2_behaviour(customer_id: int) -> dict:
    """Analyse customer transaction behaviour over the last 90 days.

    Rules:
        1. Amount spike     — latest txn > 3x average        (+40)
        2. Frequency spike  — this week > 2.5x weekly avg    (+30)
        3. Geographic spread — unique cities > 5              (+20)
        4. High-value count — > 3 txns above threshold       (+10)
        5. Merchant risk    — >= 2 txns at high-risk merchants (+15)
    """
    logger.info(f"Agent 2 — analysing customer_id={customer_id}")

    conn    = get_db()
    cur     = conn.cursor()
    since90 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
    since7  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    # Single query that fetches amount, timestamp, city, AND merchant
    cur.execute("""
        SELECT t.amount, t.timestamp, t.merchant, c.name AS city
        FROM transactions t
        JOIN cities c ON t.city_id = c.id
        WHERE t.customer_id = ? AND t.timestamp >= ?
        ORDER BY t.timestamp DESC
    """, (customer_id, since90))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "agent": "Agent 2 — Behavioural Analysis",
            "status": "SAFE", "score": 0, "details": {},
        }

    # Extract fields
    amounts     = [r["amount"] for r in rows]
    cities      = list(set(r["city"] for r in rows))
    merchants   = [r["merchant"] for r in rows]
    count       = len(amounts)
    avg         = sum(amounts) / count
    recent_week = [r for r in rows if r["timestamp"] >= since7]
    avg_weekly  = count / (90 / 7)

    score  = 0
    alerts = []

    # Rule 1: Amount spike
    latest = amounts[0]
    if latest > avg * 3:
        score += 40
        alerts.append(
            f"Latest transaction of Rp {latest:,.0f} is {latest/avg:.1f}x above average"
        )

    # Rule 2: Frequency spike
    if len(recent_week) > avg_weekly * 2.5:
        score += 30
        alerts.append(
            f"Frequency this week ({len(recent_week)}x) is well above "
            f"the average ({avg_weekly:.1f}x/week)"
        )

    # Rule 3: Geographic dispersal
    if len(cities) > 5:
        score += 20
        alerts.append(f"Transactions occurred in {len(cities)} different cities over 90 days")

    # Rule 4: High-value count
    high_value_count = sum(1 for a in amounts if a > HIGH_VALUE_THRESHOLD)
    if high_value_count > 3:
        score += 10
        alerts.append(
            f"{high_value_count} transactions above Rp {HIGH_VALUE_THRESHOLD/1e6:.0f}M in 90 days"
        )

    # Rule 5: Merchant risk — count transactions at high-risk merchants
    merchant_risk_breakdown = {}
    for merchant_name in merchants:
        mr = classify_merchant_risk(merchant_name)
        if mr:
            label = mr["label"]
            merchant_risk_breakdown[label] = merchant_risk_breakdown.get(label, 0) + 1

    risky_merchant_count = sum(merchant_risk_breakdown.values())
    if risky_merchant_count >= 2:
        score += 15
        breakdown_str = ", ".join(f"{k} ({v}x)" for k, v in merchant_risk_breakdown.items())
        alerts.append(
            f"{risky_merchant_count} transactions at high-risk merchants: {breakdown_str}"
        )

    # Final result
    status = _score_to_status(min(score, 100))
    logger.info(f"Agent 2 done — status={status} score={score}")

    return {
        "agent":  "Agent 2 — Behavioural Analysis",
        "status": status,
        "score":  min(score, 100),
        "details": {
            "lookback_days":           90,
            "total_transactions":      count,
            "average_amount":          round(avg),
            "max_amount":              round(max(amounts)),
            "min_amount":              round(min(amounts)),
            "unique_cities":           len(cities),
            "recent_week_count":       len(recent_week),
            "avg_weekly":              round(avg_weekly, 1),
            "high_value_count":        high_value_count,
            "risky_merchant_count":    risky_merchant_count,
            "merchant_risk_breakdown": merchant_risk_breakdown,
            "alerts":                  alerts,
        },
    }


# ════════════════════════════════════════════════════════════════
#  AGENT 3 — Verdict Aggregator
# ════════════════════════════════════════════════════════════════
def agent_3_conclusion(customer_id: int, a1: dict, a2: dict) -> dict:
    """Combine Agent 1 (60%) + Agent 2 (40%) into a final verdict."""
    combined = round((a1["score"] * 0.6) + (a2["score"] * 0.4), 1)
    status   = _score_to_status(combined)

    logger.info(f"Agent 3 — customer={customer_id} combined={combined} verdict={status}")

    verdicts = {
        "FRAUD": {
            "action":         "🔴 STOP — Block card and contact customer immediately!",
            "recommendation": "Fraud pattern detected. Freeze account and verify identity.",
            "color":          "red",
        },
        "WARNING": {
            "action":         "🟡 WARNING — Send verification notification to customer",
            "recommendation": "Suspicious pattern detected. Request SMS/email confirmation before proceeding.",
            "color":          "orange",
        },
        "SAFE": {
            "action":         "🟢 SAFE — Transaction may proceed",
            "recommendation": "No suspicious patterns detected. Normal activity.",
            "color":          "green",
        },
    }

    v = verdicts[status]
    return {
        "agent":          "Agent 3 — Verdict Aggregator",
        "customer_id":    customer_id,
        "final_status":   status,
        "color":          v["color"],
        "combined_score": combined,
        "action":         v["action"],
        "recommendation": v["recommendation"],
        "weights": {
            "agent1_weight": "60%",
            "agent2_weight": "40%",
            "agent1_score":  a1["score"],
            "agent2_score":  a2["score"],
        },
        "thresholds": {
            "fraud":   FRAUD_SCORE_THRESHOLD,
            "warning": WARNING_SCORE_THRESHOLD,
        },
    }


# ════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ════════════════════════════════════════════════════════════════
def _build_merchant_risk_summary(customer_id: int) -> dict:
    """Build a summary of merchant risk categories from recent transactions."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT t.merchant FROM transactions t
        WHERE t.customer_id = ?
        ORDER BY t.timestamp DESC LIMIT 50
    """, (customer_id,))
    rows = cur.fetchall()
    conn.close()

    summary = {}
    for row in rows:
        mr = classify_merchant_risk(row[0])
        if mr:
            label = mr["label"]
            if label not in summary:
                summary[label] = {"count": 0, "level": mr["level"]}
            summary[label]["count"] += 1
    return summary


def run_fraud_analysis(customer_id: int) -> dict:
    """Run the full 3-agent fraud analysis pipeline for one customer.

    Returns a dict containing customer info, all 3 agent results,
    and a merchant risk summary.
    """
    logger.info(f"=== Fraud Analysis Pipeline — customer_id={customer_id} ===")

    # Run all 3 agents
    a1 = agent_1_location_time(customer_id)
    a2 = agent_2_behaviour(customer_id)
    a3 = agent_3_conclusion(customer_id, a1, a2)

    # Fetch customer info
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT cu.name, c.name AS home_city, cu.salary
        FROM customers cu
        JOIN cities c ON cu.home_city_id = c.id
        WHERE cu.id = ?
    """, (customer_id,))
    row = cur.fetchone()
    conn.close()

    # Build merchant risk summary
    merchant_risk_summary = _build_merchant_risk_summary(customer_id)

    return {
        "customer_id":           customer_id,
        "customer_name":         CUSTOMERS_MAP.get(customer_id, "Unknown"),
        "home_city":             row["home_city"] if row else "Unknown",
        "salary":                row["salary"]    if row else "Unknown",
        "analysed_at":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "merchant_risk_summary": merchant_risk_summary,
        "agent1":                a1,
        "agent2":                a2,
        "agent3":                a3,
    }