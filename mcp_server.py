"""
MCP Server — Banking Fraud & Sales Analytics
Expose tools ke Cursor / Claude Desktop via Model Context Protocol
"""

import asyncio
import json
import sqlite3
import math
import sys
import os
from datetime import datetime, timedelta
from typing import Any

# MCP SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Path setup ──────────────────────────────────────────────────
# Supaya bisa import dari app/ walaupun dijalankan dari mana saja
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.services.fraud_agents import classify_merchant_risk

DB_PATH = os.path.join(BASE_DIR, "data", "banking.db")

# ── Helpers ─────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # hasil query bisa diakses seperti dict
    return conn


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Hitung jarak (km) antara dua titik koordinat."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fmt_idr(n: float) -> str:
    return f"Rp {int(n):,}".replace(",", ".")


# ── MCP Server instance ─────────────────────────────────────────
server = Server("banking-fraud-mcp")


# ════════════════════════════════════════════════════════════════
#  TOOL DEFINITIONS
# ════════════════════════════════════════════════════════════════
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        # ── 1. Daftar nasabah ──────────────────────────────────
        types.Tool(
            name="get_customers",
            description=(
                "Ambil daftar semua nasabah beserta info dasar "
                "(id, nama, kota asal, gaji)."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),

        # ── 2. Riwayat transaksi nasabah ───────────────────────
        types.Tool(
            name="get_transactions",
            description=(
                "Ambil riwayat transaksi terbaru seorang nasabah. "
                "Gunakan customer_id dari get_customers."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "ID nasabah (1–10)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Jumlah transaksi yang diambil (default 20)",
                        "default": 20,
                    },
                },
                "required": ["customer_id"],
            },
        ),

        # ── 3. Agent 1 — Analisis lokasi & waktu ──────────────
        types.Tool(
            name="analyze_location_time",
            description=(
                "Agent 1: Deteksi transaksi mencurigakan berdasarkan jarak "
                "geografis dan selisih waktu antar transaksi. "
                "Contoh: transaksi di Jakarta lalu 30 menit kemudian di Surabaya "
                "(800 km) adalah mustahil secara fisik."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "ID nasabah yang akan dianalisis",
                    },
                },
                "required": ["customer_id"],
            },
        ),

        # ── 4. Agent 2 — Analisis perilaku ────────────────────
        types.Tool(
            name="analyze_behaviour",
            description=(
                "Agent 2: Analisis pola perilaku transaksi nasabah dalam "
                "3 bulan terakhir — jumlah, rata-rata, max, min, "
                "frekuensi per minggu, dan kota yang dikunjungi."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "ID nasabah yang akan dianalisis",
                    },
                },
                "required": ["customer_id"],
            },
        ),

        # ── 5. Agent 3 — Kesimpulan fraud ─────────────────────
        types.Tool(
            name="run_fraud_analysis",
            description=(
                "Jalankan full fraud analysis (Agent 1 + 2 + 3) untuk seorang "
                "nasabah. Menghasilkan verdict: AMAN / WARNING / FRAUD "
                "beserta skor risiko dan rekomendasi tindakan."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "ID nasabah (1–10)",
                    },
                },
                "required": ["customer_id"],
            },
        ),

        # ── 6. Ringkasan sales ─────────────────────────────────
        types.Tool(
            name="get_sales_summary",
            description=(
                "Ambil ringkasan data penjualan: total revenue, jumlah transaksi, "
                "breakdown per kategori & region, tren bulanan, top 10 produk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "months": {
                        "type": "integer",
                        "description": "Periode dalam bulan (default 6)",
                        "default": 6,
                    },
                },
                "required": [],
            },
        ),

        # ── 7. Query sales kustom ──────────────────────────────
        types.Tool(
            name="query_sales",
            description=(
                "Query data sales dengan filter: kategori, region, atau rentang tanggal. "
                "Hasilkan tabulasi statistik penjualan."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter kategori: Elektronik, Groceries, Fashion",
                    },
                    "region": {
                        "type": "string",
                        "description": "Filter region: Jakarta, Surabaya, Bandung, Medan, Semarang",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Rentang hari ke belakang (default 90)",
                        "default": 90,
                    },
                },
                "required": [],
            },
        ),

        # ── 8. Daftar kota + koordinat ─────────────────────────
        types.Tool(
            name="get_cities",
            description=(
                "Ambil daftar semua kota di database beserta koordinat "
                "latitude/longitude. Berguna untuk perhitungan jarak."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),

        # ── 9. Hitung jarak dua kota ───────────────────────────
        types.Tool(
            name="calculate_distance",
            description=(
                "Hitung jarak (km) dan estimasi waktu perjalanan minimum "
                "antara dua kota Indonesia."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "city_a": {
                        "type": "string",
                        "description": "Nama kota pertama (contoh: Jakarta)",
                    },
                    "city_b": {
                        "type": "string",
                        "description": "Nama kota kedua (contoh: Surabaya)",
                    },
                },
                "required": ["city_a", "city_b"],
            },
        ),
    ]


# ════════════════════════════════════════════════════════════════
#  TOOL IMPLEMENTATIONS
# ════════════════════════════════════════════════════════════════
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:

    # ── 1. get_customers ────────────────────────────────────────
    if name == "get_customers":
        conn = get_db()
        rows = conn.execute("""
            SELECT cu.id, cu.name, cu.salary, c.name as home_city
            FROM customers cu
            JOIN cities c ON cu.home_city_id = c.id
        """).fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 2. get_transactions ─────────────────────────────────────
    elif name == "get_transactions":
        cid   = arguments["customer_id"]
        limit = arguments.get("limit", 20)
        conn  = get_db()
        rows  = conn.execute("""
            SELECT t.id, t.amount, t.timestamp, t.merchant, t.is_flagged,
                   c.name as city, c.lat, c.lon
            FROM transactions t
            JOIN cities c ON t.city_id = c.id
            WHERE t.customer_id = ?
            ORDER BY t.timestamp DESC
            LIMIT ?
        """, (cid, limit)).fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 3. analyze_location_time ────────────────────────────────
    elif name == "analyze_location_time":
        cid  = arguments["customer_id"]
        conn = get_db()
        rows = conn.execute("""
            SELECT t.id, t.amount, t.timestamp, t.merchant,
                   c.name as city, c.lat, c.lon
            FROM transactions t
            JOIN cities c ON t.city_id = c.id
            WHERE t.customer_id = ?
            ORDER BY t.timestamp DESC
            LIMIT 10
        """, (cid,)).fetchall()
        conn.close()
        rows = [dict(r) for r in rows]

        suspicious = []
        max_score  = 0

        for i in range(len(rows) - 1):
            t1, t2 = rows[i], rows[i + 1]
            ts1 = datetime.strptime(t1["timestamp"], "%Y-%m-%d %H:%M:%S")
            ts2 = datetime.strptime(t2["timestamp"], "%Y-%m-%d %H:%M:%S")
            diff_hours = abs((ts1 - ts2).total_seconds() / 3600)
            dist_km    = haversine(t1["lat"], t1["lon"], t2["lat"], t2["lon"])

            if dist_km < 1:
                continue

            min_travel = (dist_km / 800 + 3) if dist_km > 300 else (dist_km / 80)
            is_susp    = diff_hours < min_travel and dist_km > 10
            
            mr = classify_merchant_risk(t1["merchant"])
            mr_score = mr["risk_bonus"] if mr else 0
            
            score      = 0
            if is_susp:
                score     = min(100, int((min_travel / max(diff_hours, 0.01)) * 30) + mr_score)
                max_score = max(max_score, score)

            suspicious.append({
                "dari":           t2["city"],
                "ke":             t1["city"],
                "waktu_dari":     t2["timestamp"],
                "waktu_ke":       t1["timestamp"],
                "jarak_km":       round(dist_km, 1),
                "selisih_jam":    round(diff_hours, 2),
                "min_perjalanan": round(min_travel, 2),
                "mencurigakan":   is_susp,
                "merchant_risk":  mr["label"] if mr else None,
                "risk_score":     score,
            })

        status = "FRAUD" if max_score >= 70 else "WARNING" if max_score >= 30 else "AMAN"
        result = {
            "customer_id":       cid,
            "agent":             "Agent 1 — Lokasi & Waktu",
            "status":            status,
            "risk_score":        max_score,
            "pasang_mencurigakan": sum(1 for s in suspicious if s["mencurigakan"]),
            "detail":            suspicious,
        }
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 4. analyze_behaviour ────────────────────────────────────
    elif name == "analyze_behaviour":
        cid        = arguments["customer_id"]
        since      = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        week_ago   = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        conn       = get_db()
        rows       = conn.execute("""
            SELECT t.amount, t.timestamp, t.merchant, c.name as city
            FROM transactions t
            JOIN cities c ON t.city_id = c.id
            WHERE t.customer_id = ? AND t.timestamp >= ?
            ORDER BY t.timestamp DESC
        """, (cid, since)).fetchall()
        conn.close()
        rows = [dict(r) for r in rows]

        if not rows:
            return [types.TextContent(type="text", text=json.dumps({"status": "AMAN", "detail": "Tidak ada data"}))]

        amounts     = [r["amount"] for r in rows]
        avg         = sum(amounts) / len(amounts)
        recent_week = [r for r in rows if r["timestamp"] >= week_ago]
        cities      = list(set(r["city"] for r in rows))
        score       = 0
        alerts      = []

        if amounts[0] > avg * 3:
            score += 40
            alerts.append(f"Transaksi terakhir {fmt_idr(amounts[0])} adalah {amounts[0]/avg:.1f}x di atas rata-rata")

        avg_weekly = len(amounts) / (90 / 7)
        if len(recent_week) > avg_weekly * 2.5:
            score += 30
            alerts.append(f"Frekuensi minggu ini ({len(recent_week)}x) jauh di atas rata-rata ({avg_weekly:.1f}x/minggu)")

        if len(cities) > 5:
            score += 20
            alerts.append(f"Transaksi terjadi di {len(cities)} kota berbeda dalam 3 bulan")

        merchant_risks = [classify_merchant_risk(r["merchant"]) for r in rows]
        merchant_risks = [mr for mr in merchant_risks if mr] # filter None
        risky_merchant_count = len(merchant_risks)

        if risky_merchant_count >= 2:
            score += 15
            alerts.append(f"{risky_merchant_count} transaksi di merchant berisiko tinggi terdeteksi")

        status = "FRAUD" if score >= 70 else "WARNING" if score >= 30 else "AMAN"
        result = {
            "customer_id":        cid,
            "agent":              "Agent 2 — Analisis Perilaku",
            "status":             status,
            "risk_score":         min(score, 100),
            "total_transaksi":    len(amounts),
            "rata_rata":          fmt_idr(avg),
            "tertinggi":          fmt_idr(max(amounts)),
            "terendah":           fmt_idr(min(amounts)),
            "kota_unik":          len(cities),
            "transaksi_pekan_ini": len(recent_week),
            "transaksi_merchant_risiko_tinggi": risky_merchant_count,
            "alerts":             alerts,
        }
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 5. run_fraud_analysis ───────────────────────────────────
    elif name == "run_fraud_analysis":
        cid = arguments["customer_id"]

        # Panggil Agent 1 & 2 secara internal
        a1_resp = await call_tool("analyze_location_time", {"customer_id": cid})
        a2_resp = await call_tool("analyze_behaviour",     {"customer_id": cid})
        a1 = json.loads(a1_resp[0].text)
        a2 = json.loads(a2_resp[0].text)

        # Agent 3 — combined score
        combined = (a1["risk_score"] * 0.6) + (a2["risk_score"] * 0.4)

        if combined >= 65:
            verdict    = "FRAUD"
            action     = "🔴 STOP — Blokir kartu dan hubungi nasabah segera!"
            rekomendasi = "Pola penipuan terdeteksi. Bekukan akun, lakukan verifikasi identitas."
        elif combined >= 35:
            verdict    = "WARNING"
            action     = "🟡 WARNING — Kirim notifikasi verifikasi ke nasabah"
            rekomendasi = "Ada pola mencurigakan. Minta konfirmasi via SMS/email sebelum lanjutkan."
        else:
            verdict    = "AMAN"
            action     = "🟢 AMAN — Transaksi dapat dilanjutkan"
            rekomendasi = "Tidak ada pola mencurigakan. Aktivitas normal."

        # Info nasabah
        conn = get_db()
        cust = conn.execute("""
            SELECT cu.name, c.name as home_city, cu.salary
            FROM customers cu JOIN cities c ON cu.home_city_id = c.id
            WHERE cu.id = ?
        """, (cid,)).fetchone()
        conn.close()

        result = {
            "customer_id":   cid,
            "nama_nasabah":  cust["name"] if cust else "Unknown",
            "kota_asal":     cust["home_city"] if cust else "Unknown",
            "verdict":       verdict,
            "combined_score": round(combined, 1),
            "action":        action,
            "rekomendasi":   rekomendasi,
            "agent1": {
                "status":     a1["status"],
                "risk_score": a1["risk_score"],
                "pasang_mencurigakan": a1["pasang_mencurigakan"],
            },
            "agent2": {
                "status":          a2["status"],
                "risk_score":      a2["risk_score"],
                "total_transaksi": a2["total_transaksi"],
                "rata_rata":       a2["rata_rata"],
                "alerts":          a2["alerts"],
            },
        }
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 6. get_sales_summary ────────────────────────────────────
    elif name == "get_sales_summary":
        months = arguments.get("months", 6)
        since  = (datetime.now() - timedelta(days=30 * months)).strftime("%Y-%m-%d")
        conn   = get_db()

        total = conn.execute(
            "SELECT SUM(amount), COUNT(*) FROM sales WHERE sale_date >= ?", (since,)
        ).fetchone()

        by_cat = conn.execute("""
            SELECT category, SUM(amount) as revenue, COUNT(*) as txn, SUM(qty) as qty
            FROM sales WHERE sale_date >= ?
            GROUP BY category ORDER BY revenue DESC
        """, (since,)).fetchall()

        by_region = conn.execute("""
            SELECT region, SUM(amount) as revenue, COUNT(*) as txn
            FROM sales WHERE sale_date >= ?
            GROUP BY region ORDER BY revenue DESC
        """, (since,)).fetchall()

        monthly = []
        for i in range(months - 1, -1, -1):
            d   = datetime.now() - timedelta(days=30 * i)
            mon = d.strftime("%Y-%m")
            row = conn.execute(
                "SELECT SUM(amount), COUNT(*) FROM sales WHERE sale_date LIKE ?",
                (f"{mon}%",)
            ).fetchone()
            monthly.append({"bulan": d.strftime("%b %Y"), "revenue": round(row[0] or 0), "transaksi": row[1] or 0})

        top_products = conn.execute("""
            SELECT product, category, SUM(amount) as revenue, SUM(qty) as qty
            FROM sales WHERE sale_date >= ?
            GROUP BY product ORDER BY revenue DESC LIMIT 10
        """, (since,)).fetchall()

        conn.close()

        result = {
            "periode":          f"{months} bulan terakhir",
            "total_revenue":    fmt_idr(total[0] or 0),
            "total_transaksi":  total[1] or 0,
            "rata_rata":        fmt_idr((total[0] or 0) / max(total[1] or 1, 1)),
            "per_kategori":     [dict(r) for r in by_cat],
            "per_region":       [dict(r) for r in by_region],
            "tren_bulanan":     monthly,
            "top_10_produk":    [dict(r) for r in top_products],
        }
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 7. query_sales ──────────────────────────────────────────
    elif name == "query_sales":
        category = arguments.get("category")
        region   = arguments.get("region")
        days     = arguments.get("days", 90)
        since    = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        where  = ["sale_date >= ?"]
        params = [since]
        if category:
            where.append("category = ?")
            params.append(category)
        if region:
            where.append("region = ?")
            params.append(region)

        where_clause = " AND ".join(where)
        conn = get_db()

        rows = conn.execute(f"""
            SELECT product, category, region, sale_date,
                   SUM(amount) as total_revenue, SUM(qty) as total_qty, COUNT(*) as txn_count
            FROM sales
            WHERE {where_clause}
            GROUP BY product, category, region
            ORDER BY total_revenue DESC
            LIMIT 50
        """, params).fetchall()

        stats = conn.execute(f"""
            SELECT COUNT(*) as total_txn,
                   SUM(amount) as total_rev,
                   AVG(amount) as avg_rev,
                   MAX(amount) as max_rev,
                   MIN(amount) as min_rev
            FROM sales WHERE {where_clause}
        """, params).fetchone()

        conn.close()

        result = {
            "filter": {"category": category, "region": region, "days": days},
            "statistik": {
                "total_transaksi": stats["total_txn"],
                "total_revenue":   fmt_idr(stats["total_rev"] or 0),
                "rata_rata":       fmt_idr(stats["avg_rev"] or 0),
                "tertinggi":       fmt_idr(stats["max_rev"] or 0),
                "terendah":        fmt_idr(stats["min_rev"] or 0),
            },
            "detail": [dict(r) for r in rows],
        }
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 8. get_cities ───────────────────────────────────────────
    elif name == "get_cities":
        conn  = get_db()
        rows  = conn.execute("SELECT id, name, lat, lon FROM cities ORDER BY name").fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    # ── 9. calculate_distance ───────────────────────────────────
    elif name == "calculate_distance":
        city_a = arguments["city_a"].strip().title()
        city_b = arguments["city_b"].strip().title()
        conn   = get_db()
        ca     = conn.execute("SELECT name, lat, lon FROM cities WHERE name LIKE ?", (f"%{city_a}%",)).fetchone()
        cb     = conn.execute("SELECT name, lat, lon FROM cities WHERE name LIKE ?", (f"%{city_b}%",)).fetchone()
        conn.close()

        if not ca or not cb:
            missing = city_a if not ca else city_b
            return [types.TextContent(type="text", text=f"Kota '{missing}' tidak ditemukan di database.")]

        dist = haversine(ca["lat"], ca["lon"], cb["lat"], cb["lon"])
        if dist > 300:
            min_travel = dist / 800 + 3   # pesawat + waktu bandara
            mode       = "pesawat"
        else:
            min_travel = dist / 80        # mobil
            mode       = "mobil"

        result = {
            "kota_a":           ca["name"],
            "kota_b":           cb["name"],
            "jarak_km":         round(dist, 1),
            "mode_perjalanan":  mode,
            "min_waktu_jam":    round(min_travel, 2),
            "penjelasan":       (
                f"Jarak {ca['name']}–{cb['name']} adalah {dist:.0f} km. "
                f"Dengan {mode}, waktu minimum yang dibutuhkan adalah "
                f"±{min_travel:.1f} jam."
            ),
        }
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    else:
        return [types.TextContent(type="text", text=f"Tool '{name}' tidak dikenal.")]


# ════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())