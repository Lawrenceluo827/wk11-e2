"""Flask frontend for the Week 11 data pipeline (Exercise 2).

Reads ``orders.db`` on every request, so any change made by the GitHub Actions
data workflow is visible as soon as the database file is pulled / refreshed.
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


def query(sql: str) -> tuple[list[str], list[dict]]:
    if not DB_PATH.exists():
        return [], []
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        columns = [c[0] for c in cursor.description] if cursor.description else []
        return columns, [dict(row) for row in cursor.fetchall()]


@app.route("/")
def index() -> str:
    order_cols, orders = query(
        f"SELECT order_id, customer_id, order_date, product, amount, currency, "
        f"amount_cny, region FROM {ORDER_TABLE} ORDER BY order_date, order_id"
    )
    summary_cols, summary = query(
        f"SELECT region, avg_amount_cny, order_count, total_amount_cny "
        f"FROM {SUMMARY_TABLE} ORDER BY avg_amount_cny DESC"
    )
    totals = {
        "orders": len(orders),
        "revenue": round(sum(r["amount_cny"] or 0 for r in orders), 2),
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
