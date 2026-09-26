"""SQLite storage: business data (orders, products), support tickets and chat history.

For a real client, swap the order/product queries for calls to their system
(Shopify, WooCommerce, a CRM, their own API). Everything else stays the same.
"""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY, name TEXT NOT NULL, price_usd REAL NOT NULL, stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY, email TEXT NOT NULL, status TEXT NOT NULL, items TEXT NOT NULL,
    total_usd REAL NOT NULL, carrier TEXT, tracking_number TEXT, estimated_delivery TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY, session_id TEXT, name TEXT, email TEXT, summary TEXT,
    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""

DEMO_PRODUCTS = [
    ("NH-LAMP-01", "Aurora Table Lamp", 49.00, 34),
    ("NH-THRW-02", "Cloudknit Throw Blanket", 69.00, 0),
    ("NH-MUG-03", "Stoneware Mug Set (4)", 32.00, 120),
    ("NH-DIFF-04", "Mist Aroma Diffuser", 39.00, 8),
    ("NH-CUSH-05", "Linen Cushion Cover", 24.00, 56),
]

DEMO_ORDERS = [
    ("NH-1001", "priya@example.com", "shipped", "Aurora Table Lamp x1, Linen Cushion Cover x2", 97.00,
     "UPS", "1Z999AA10123456784", "2026-10-02"),
    ("NH-1002", "james@example.com", "processing", "Cloudknit Throw Blanket x1", 69.00, None, None, "2026-10-06"),
    ("NH-1003", "sara@example.com", "delivered", "Stoneware Mug Set (4) x1", 32.00,
     "FedEx", "794612345678", "2026-09-20"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self._path = path
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
                conn.executemany("INSERT INTO products VALUES (?,?,?,?)", DEMO_PRODUCTS)
                conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", DEMO_ORDERS)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- business data ---

    def get_order(self, order_id: str, email: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE UPPER(order_id) = UPPER(?) AND LOWER(email) = LOWER(?)",
                (order_id.strip(), email.strip()),
            ).fetchone()
        return dict(row) if row else None

    def find_products(self, query: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE name LIKE ? OR sku LIKE ? LIMIT 5",
                (f"%{query.strip()}%", f"%{query.strip()}%"),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- tickets (human handoff) ---

    def create_ticket(self, session_id: str, name: str, email: str, summary: str) -> str:
        ticket_id = f"T-{uuid.uuid4().hex[:6].upper()}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tickets (ticket_id, session_id, name, email, summary, created_at) VALUES (?,?,?,?,?,?)",
                (ticket_id, session_id, name, email, summary, _now()),
            )
        return ticket_id

    def list_tickets(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # --- chat history ---

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                (session_id, role, content, _now()),
            )

    def get_history(self, session_id: str, turns: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, turns * 2),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
