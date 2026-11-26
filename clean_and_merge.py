"""Clean and merge the order / customer data files into an SQLite database.

Pipeline (runs locally and inside the GitHub Actions data workflow):

1. read every ``data/order*.txt`` and ``data/customer*.txt`` file
2. drop duplicated rows
3. convert ``amount`` to CNY using fixed exchange rates -> ``amount_cny``
4. join orders with customers on ``customer_id``
5. write the merged table to SQLite
6. build a summary table: average ``amount_cny`` per region

Because ``order*.txt`` is globbed, simply dropping a new file such as
``data/order_new.txt`` into the folder is enough: the next run merges it.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "orders.db"

# Fixed conversion rates used in the exercise (1 unit of currency -> CNY)
EXCHANGE_RATES = {"USD": 6.9, "EUR": 7.5, "CNY": 1.0, "JPY": 0.05}

ORDER_TABLE = "orders_merged"
SUMMARY_TABLE = "region_summary"

# Tolerated column-name aliases so the script also works with the official files.
ALIASES = {
    "order_id": ["order_id", "orderid", "id", "order_no", "order no", "order number"],
    "customer_id": ["customer_id", "customerid", "cust_id", "customer", "customer id"],
    "order_date": ["order_date", "date", "order date", "orderdate"],
    "product": ["product", "item", "product_name", "description"],
    "amount": ["amount", "total", "price", "order_amount"],
    "currency": ["currency", "ccy", "curr"],
    "customer_name": ["customer_name", "name", "cust_name", "customer name"],
    "region": ["region", "area", "city", "district", "location"],
    "signup_date": ["signup_date", "join_date", "signup", "register_date"],
}


def read_txt(path: Path) -> pd.DataFrame:
    """Read a txt file that may be comma, tab or pipe separated."""
    df = pd.read_csv(
        path,
        sep=None,          # sniff the delimiter
        engine="python",
        dtype=str,
        encoding="utf-8-sig",
    )
    df.columns = [str(c).strip().lower().replace("-", "_") for c in df.columns]
    return df


def standardise(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Rename known aliases to the canonical column names."""
    rename = {}
    for canonical, candidates in ALIASES.items():
        for col in df.columns:
            if col in candidates:
                rename[col] = canonical
                break
    out = df.rename(columns=rename)
    if mapping:
        out = out.rename(columns=mapping)
    return out


def load_group(pattern: str, required: list[str]) -> pd.DataFrame:
    files = sorted(DATA_DIR.glob(pattern))
    if not files:
        raise SystemExit(f"[error] no file matched data/{pattern}")

    frames = []
    for path in files:
        df = read_txt(path)
        df = standardise(df, mapping={})
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SystemExit(f"[error] {path.name} is missing columns {missing}; found {list(df.columns)}")
        frames.append(df)
        print(f"[read] {path.name}: {len(df)} rows")

    return pd.concat(frames, ignore_index=True)


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    before = len(orders)
    orders = orders.drop_duplicates().copy()
    print(f"[clean] dropped {before - len(orders)} duplicated order rows")

    orders["customer_id"] = orders["customer_id"].str.strip()
    orders["currency"] = orders["currency"].str.strip().str.upper()
    orders["amount"] = pd.to_numeric(orders["amount"].astype(str).str.replace(",", ""), errors="coerce")

    unknown = set(orders["currency"].unique()) - set(EXCHANGE_RATES)
    if unknown:
        raise SystemExit(f"[error] unsupported currency codes: {sorted(unknown)}")

    orders["amount_cny"] = (orders["amount"] * orders["currency"].map(EXCHANGE_RATES)).round(2)
    return orders


def main() -> int:
    if not DATA_DIR.exists():
        raise SystemExit(f"[error] data folder not found: {DATA_DIR}")

    customers = load_group("customer*.txt", required=["customer_id", "region"])
    customers = customers.drop_duplicates(subset=["customer_id"], keep="first")
    print(f"[clean] customers after de-duplication: {len(customers)}")

    orders = load_group("order*.txt", required=["customer_id", "amount", "currency"])
    orders = clean_orders(orders)

    merged = orders.merge(customers, on="customer_id", how="left", suffixes=("", "_customer"))
    merged["region"] = merged["region"].fillna("Unknown")
    print(f"[merge] merged rows: {len(merged)}")

    summary = (
        merged.groupby("region", as_index=False)["amount_cny"]
        .agg(avg_amount_cny="mean", order_count="count", total_amount_cny="sum")
        .round({"avg_amount_cny": 2, "total_amount_cny": 2})
        .sort_values("avg_amount_cny", ascending=False)
    )
    print("[summary] average amount_cny per region:")
    print(summary.to_string(index=False))

    with sqlite3.connect(DB_PATH) as conn:
        merged.to_sql(ORDER_TABLE, conn, if_exists="replace", index=False)
        summary.to_sql(SUMMARY_TABLE, conn, if_exists="replace", index=False)
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{ORDER_TABLE}_customer "
            f"ON {ORDER_TABLE}(customer_id)"
        )
        conn.commit()

    print(f"[write] {DB_PATH.name}: {ORDER_TABLE} ({len(merged)} rows), "
          f"{SUMMARY_TABLE} ({len(summary)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
