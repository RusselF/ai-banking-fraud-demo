"""
database.py
===========
Database initialization and dummy data seeding for the Banking Fraud Detection demo.

Tables: cities, customers, transactions, sales
Data is only inserted if the table is empty (safe to re-run).
"""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "data/banking.db"


# ════════════════════════════════════════════════════════════════
#  SEED DATA CONSTANTS
# ════════════════════════════════════════════════════════════════

# 20 kota Indonesia dengan koordinat
CITIES = [
    ("Jakarta",     -6.2088, 106.8456),
    ("Surabaya",    -7.2575, 112.7521),
    ("Bandung",     -6.9175, 107.6191),
    ("Medan",        3.5952,  98.6722),
    ("Semarang",    -6.9932, 110.4203),
    ("Makassar",    -5.1477, 119.4327),
    ("Palembang",   -2.9761, 104.7754),
    ("Tangerang",   -6.1781, 106.6297),
    ("Depok",       -6.4025, 106.7942),
    ("Bekasi",      -6.2349, 106.9896),
    ("Bogor",       -6.5971, 106.8060),
    ("Yogyakarta",  -7.7956, 110.3695),
    ("Denpasar",    -8.6500, 115.2167),
    ("Malang",      -7.9666, 112.6326),
    ("Batam",        1.0456, 104.0305),
    ("Pekanbaru",    0.5071, 101.4478),
    ("Balikpapan",  -1.2379, 116.8529),
    ("Manado",       1.4748, 124.8421),
    ("Padang",      -0.9492, 100.3543),
    ("Pontianak",   -0.0263, 109.3425),
]

# 10 nasabah demo (id, nama, gaji)
CUSTOMERS = [
    (1,  "Budi Santoso",   "Rp 8.500.000"),
    (2,  "Siti Rahayu",    "Rp 12.000.000"),
    (3,  "Agus Permana",   "Rp 6.750.000"),
    (4,  "Dewi Lestari",   "Rp 15.000.000"),
    (5,  "Rizky Pratama",  "Rp 9.200.000"),
    (6,  "Rina Wulandari", "Rp 7.300.000"),
    (7,  "Hendra Wijaya",  "Rp 22.000.000"),
    (8,  "Yanti Kusuma",   "Rp 5.500.000"),
    (9,  "Doni Setiawan",  "Rp 11.800.000"),
    (10, "Maya Putri",     "Rp 8.900.000"),
]

# Kota asal tiap nasabah (index sesuai CITIES)
HOME_CITIES = [1, 1, 3, 1, 3, 1, 2, 5, 1, 8]

# Nasabah yang akan di-inject transaksi mencurigakan
SUSPICIOUS_CUSTOMERS = [2, 5, 7]

# Merchant biasa
MERCHANTS_NORMAL = [
    "Indomaret", "Alfamart", "Giant", "Hypermart", "Tokopedia",
    "Shopee", "Lazada", "Grab", "Gojek", "McDonald's",
    "KFC", "Pizza Hut", "SPBU Pertamina", "PLN Mobile",
    "Apotik K24", "RS Siloam",
]

# Merchant berisiko tinggi (fraud detection flag)
MERCHANTS_HIGH_RISK = [
    "Toko Elektronik Jaya", "Toko Emas Berkah",
    "Perhiasan Mulia", "ATM Center Mall",
]

# Merchant travel
MERCHANTS_TRAVEL = ["Hotel Santika", "Garuda Indonesia", "Lion Air"]

# Semua merchant (gabungan)
ALL_MERCHANTS = MERCHANTS_NORMAL + MERCHANTS_HIGH_RISK + MERCHANTS_TRAVEL

# Produk untuk tabel sales
PRODUCTS = [
    ("Laptop ASUS",    "Elektronik"),
    ("HP Samsung",     "Elektronik"),
    ("iPad",           "Elektronik"),
    ("AC Sharp",       "Elektronik"),
    ("Kulkas LG",      "Elektronik"),
    ("Beras 5kg",      "Groceries"),
    ("Minyak Goreng",  "Groceries"),
    ("Susu Formula",   "Groceries"),
    ("Kemeja Batik",   "Fashion"),
    ("Sepatu Nike",    "Fashion"),
    ("Tas Ransel",     "Fashion"),
]

SALES_REGIONS = ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang"]

PRICE_RANGES = {
    "Elektronik": (500_000, 15_000_000),
    "Groceries":  (20_000,  200_000),
    "Fashion":    (100_000, 2_000_000),
}


# ════════════════════════════════════════════════════════════════
#  SCHEMA CREATION
# ════════════════════════════════════════════════════════════════
def _create_tables(cur: sqlite3.Cursor):
    """Create all tables if they don't exist."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            lat  REAL NOT NULL,
            lon  REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id           INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            salary       TEXT,
            home_city_id INTEGER,
            FOREIGN KEY (home_city_id) REFERENCES cities(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount      REAL NOT NULL,
            city_id     INTEGER NOT NULL,
            merchant    TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            is_flagged  INTEGER DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (city_id)     REFERENCES cities(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            product   TEXT NOT NULL,
            category  TEXT NOT NULL,
            amount    REAL NOT NULL,
            qty       INTEGER NOT NULL,
            region    TEXT NOT NULL,
            sale_date TEXT NOT NULL
        )
    """)


# ════════════════════════════════════════════════════════════════
#  DATA SEEDING
# ════════════════════════════════════════════════════════════════
def _seed_cities(cur: sqlite3.Cursor, conn: sqlite3.Connection):
    """Insert city data if table is empty."""
    if cur.execute("SELECT COUNT(*) FROM cities").fetchone()[0] > 0:
        return
    cur.executemany(
        "INSERT INTO cities (id, name, lat, lon) VALUES (?, ?, ?, ?)",
        [(i + 1, name, lat, lon) for i, (name, lat, lon) in enumerate(CITIES)],
    )
    conn.commit()


def _seed_customers(cur: sqlite3.Cursor, conn: sqlite3.Connection):
    """Insert customer data if table is empty."""
    if cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
        return
    for i, (cid, name, salary) in enumerate(CUSTOMERS):
        cur.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?)",
            (cid, name, salary, HOME_CITIES[i]),
        )
    conn.commit()


def _generate_normal_transactions(cust_id: int, home_city: int, now: datetime) -> list:
    """Generate 20-40 normal transactions for one customer."""
    txns = []
    for _ in range(random.randint(20, 40)):
        days_ago = random.randint(0, 90)
        ts = now - timedelta(
            days=days_ago,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        # 85% chance di kota asal, 15% kota lain
        city = home_city if random.random() < 0.85 else random.randint(1, len(CITIES))
        amount = round(random.uniform(50_000, 2_000_000), -3)

        txns.append((
            cust_id, amount, city,
            random.choice(ALL_MERCHANTS),
            ts.strftime("%Y-%m-%d %H:%M:%S"), 0,
        ))
    return txns


def _generate_suspicious_transactions(cust_id: int, home_city: int, now: datetime) -> list:
    """Generate suspicious transactions for flagged customers.

    Includes:
    - 2 rapid transactions 800km apart (15-45 min, physically impossible)
    - 2-4 additional high-risk merchant transactions
    """
    txns = []

    # Rapid impossible-travel pair: Jakarta → Surabaya in minutes
    ts1 = now - timedelta(days=random.randint(1, 10), hours=2)
    ts2 = ts1 + timedelta(minutes=random.randint(15, 45))

    txns.append((
        cust_id,
        round(random.uniform(500_000, 5_000_000), -3),
        1,  # Jakarta
        random.choice(MERCHANTS_HIGH_RISK),
        ts1.strftime("%Y-%m-%d %H:%M:%S"), 1,  # is_flagged = 1
    ))
    txns.append((
        cust_id,
        round(random.uniform(500_000, 5_000_000), -3),
        2,  # Surabaya (800km away)
        random.choice(MERCHANTS_HIGH_RISK),
        ts2.strftime("%Y-%m-%d %H:%M:%S"), 1,  # is_flagged = 1
    ))

    # Additional high-risk merchant transactions (normal timeframes)
    for _ in range(random.randint(2, 4)):
        days_ago = random.randint(0, 60)
        ts = now - timedelta(days=days_ago, hours=random.randint(0, 23))
        txns.append((
            cust_id,
            round(random.uniform(1_000_000, 8_000_000), -3),
            home_city,
            random.choice(MERCHANTS_HIGH_RISK),
            ts.strftime("%Y-%m-%d %H:%M:%S"), 0,
        ))

    return txns


def _seed_transactions(cur: sqlite3.Cursor, conn: sqlite3.Connection):
    """Generate and insert transaction data if table is empty."""
    if cur.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] > 0:
        return

    now  = datetime.now()
    txns = []

    for cust_id in range(1, 11):
        home_city = HOME_CITIES[cust_id - 1]

        # Normal transactions for all customers
        txns.extend(_generate_normal_transactions(cust_id, home_city, now))

        # Suspicious transactions for flagged customers
        if cust_id in SUSPICIOUS_CUSTOMERS:
            txns.extend(_generate_suspicious_transactions(cust_id, home_city, now))

    cur.executemany(
        "INSERT INTO transactions "
        "(customer_id, amount, city_id, merchant, timestamp, is_flagged) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        txns,
    )
    conn.commit()


def _seed_sales(cur: sqlite3.Cursor, conn: sqlite3.Connection):
    """Generate and insert sales data if table is empty."""
    if cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0] > 0:
        return

    now   = datetime.now()
    sales = []

    for _ in range(500):
        product, category = random.choice(PRODUCTS)
        region    = random.choice(SALES_REGIONS)
        days_ago  = random.randint(0, 180)
        sale_date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        qty       = random.randint(1, 20)

        price_min, price_max = PRICE_RANGES[category]
        amount = round(random.uniform(price_min, price_max) * qty, -3)

        sales.append((product, category, amount, qty, region, sale_date))

    cur.executemany(
        "INSERT INTO sales "
        "(product, category, amount, qty, region, sale_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        sales,
    )
    conn.commit()


# ════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════
def init_db():
    """Initialize the database: create tables and seed with dummy data."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    _create_tables(cur)
    conn.commit()

    _seed_cities(cur, conn)
    _seed_customers(cur, conn)
    _seed_transactions(cur, conn)
    _seed_sales(cur, conn)

    conn.close()
    print("✅ Database initialized with dummy data!")


if __name__ == "__main__":
    init_db()