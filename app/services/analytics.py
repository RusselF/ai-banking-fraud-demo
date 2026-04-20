import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/banking.db"


def get_db():
    return sqlite3.connect(DB_PATH)


def get_sales_summary() -> dict:
    conn = get_db()
    cur = conn.cursor()

    # Total revenue
    cur.execute("SELECT SUM(amount), COUNT(*) FROM sales")
    total_rev, total_txn = cur.fetchone()

    # By category
    cur.execute("SELECT category, SUM(amount), COUNT(*) FROM sales GROUP BY category ORDER BY SUM(amount) DESC")
    by_cat = [{"category": r[0], "revenue": round(r[1]), "count": r[2]} for r in cur.fetchall()]

    # By region
    cur.execute("SELECT region, SUM(amount), COUNT(*) FROM sales GROUP BY region ORDER BY SUM(amount) DESC")
    by_region = [{"region": r[0], "revenue": round(r[1]), "count": r[2]} for r in cur.fetchall()]

    # Monthly trend (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        d = datetime.now() - timedelta(days=30 * i)
        month_str = d.strftime("%Y-%m")
        cur.execute("SELECT SUM(amount), COUNT(*) FROM sales WHERE sale_date LIKE ?", (f"{month_str}%",))
        rev, cnt = cur.fetchone()
        monthly.append({"month": d.strftime("%b %Y"), "revenue": round(rev or 0), "count": cnt or 0})

    # Top products
    cur.execute("""
        SELECT product, category, SUM(amount) as total, SUM(qty) as qty_total
        FROM sales GROUP BY product ORDER BY total DESC LIMIT 10
    """)
    top_products = [{"product": r[0], "category": r[1], "revenue": round(r[2]), "qty": r[3]} for r in cur.fetchall()]

    conn.close()

    return {
        "total_revenue": round(total_rev or 0),
        "total_transactions": total_txn or 0,
        "avg_transaction": round((total_rev or 0) / max(total_txn or 1, 1)),
        "by_category": by_cat,
        "by_region": by_region,
        "monthly_trend": monthly,
        "top_products": top_products
    }


def get_all_transactions(customer_id: int) -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.amount, t.timestamp, t.merchant, t.is_flagged,
               c.name as city_name, c.lat, c.lon
        FROM transactions t
        JOIN cities c ON t.city_id = c.id
        WHERE t.customer_id = ?
        ORDER BY t.timestamp DESC
        LIMIT 30
    """, (customer_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "amount": r[1], "timestamp": r[2], "merchant": r[3],
             "flagged": bool(r[4]), "city": r[5], "lat": r[6], "lon": r[7]} for r in rows]


def get_cities_map() -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, lat, lon FROM cities")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "lat": r[2], "lon": r[3]} for r in rows]