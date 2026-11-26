"""Flask frontend for the Week 11 data pipeline (Exercise 2).

Reads ``orders.db`` on every request, so any change made by the GitHub Actions
data workflow is visible as soon as the database file is pulled / refreshed.

The page adapts to whatever columns exist in the database, so it works both
with the official minimal schema (order_id, customer_id, amount, currency,
amount_cny, customer_name, region) and with richer versions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "orders.db"

ORDER_TABLE = "orders_merged"
SUMMARY_TABLE = "region_summary"

app = Flask(__name__)


def db_version() -> float:
    """Last-modified timestamp of the database, used by the page to auto-reload."""
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


def fetch_table(table: str) -> tuple[list[str], list[dict]]:
    """SELECT * from a table and return (columns, rows)."""
    if not DB_PATH.exists():
        return [], []
    try:
        with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT * FROM {table}")
            columns = [d[0] for d in cursor.description] if cursor.description else []
            return columns, [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        return [], []


def sort_rows(columns: list[str], rows: list[dict], numeric: str | None = None) -> list[dict]:
    """Sort by date/id when those columns exist, otherwise by a numeric column."""
    keys = [c for c in ("order_date", "order_id") if c in columns]
    if keys:
        return sorted(rows, key=lambda r: tuple(str(r.get(k) or "") for k in keys))
    if numeric and numeric in columns:
        return sorted(rows, key=lambda r: r.get(numeric) or 0, reverse=True)
    return rows


@app.route("/")
def index() -> str:
    order_cols, orders = fetch_table(ORDER_TABLE)
    orders = sort_rows(order_cols, orders)

    summary_cols, summary = fetch_table(SUMMARY_TABLE)
    summary = sort_rows(summary_cols, summary, numeric="avg_amount_cny")

    revenue = sum(r.get("amount_cny") or 0 for r in orders)
    totals = {
        "orders": len(orders),
        "revenue": round(revenue, 2),
        "regions": len(summary),
    }
    return render_template(
        "index.html",
        order_cols=order_cols,
        orders=orders,
        summary_cols=summary_cols,
        summary=summary,
        totals=totals,
        db_exists=DB_PATH.exists(),
    )


@app.route("/api/version")
def api_version():
    return jsonify({"version": db_version()})


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "database": DB_PATH.name, "exists": DB_PATH.exists()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
