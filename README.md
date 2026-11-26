# wk11-e2 — Data pipeline hands-on (MIS2001 Week 11)

Flask + SQLite application whose database is rebuilt automatically by a
**GitHub Actions data workflow** whenever something inside `data/` is pushed.

## Structure

```
wk11_e2/
├── data/                     # source txt files (pushing here triggers the workflow)
│   ├── order.txt
│   └── customer.txt
├── clean_and_merge.py        # read → dedupe → CNY → join → SQLite → summary
├── app.py                    # Flask frontend (reads orders.db on every request)
├── templates/index.html      # merged orders table + avg amount_cny per region
├── orders.db                 # generated SQLite database (committed by the workflow)
└── .github/workflows/data-pipeline.yml
```

## Run locally

```bash
pip install -r requirements.txt
python clean_and_merge.py     # builds orders.db
python app.py                 # http://127.0.0.1:5000
```

Data rules applied by `clean_and_merge.py`:

| Step | Rule |
| --- | --- |
| Read | every `data/order*.txt` and `data/customer*.txt` (delimiter auto-detected) |
| Clean | `drop_duplicates()` on orders; one row per `customer_id` |
| Convert | `amount_cny = amount × rate` — USD 6.9, EUR 7.5, CNY 1.0, JPY 0.05 |
| Merge | orders ⟕ customers on `customer_id` (region added) |
| Store | tables `orders_merged` and `region_summary` in `orders.db` |
| Summary | `avg(amount_cny)`, order count and total per `region` |

Official course files use the minimal schema and are supported as-is:

```
order.txt     order_id,customer_id,amount,currency
customer.txt  customer_id,customer_name,region
```

The Flask page adapts to the columns that actually exist, so no date/product
columns are required.

## Demonstrate the pipeline (step F of the handout)

1. Create `data/order_new.txt` with one or two extra records:

   ```csv
   order_id,customer_id,order_date,product,amount,currency
   O2001,C002,2024-06-11,Laser Printer,210.00,USD
   O2002,C005,2024-06-11,Label Printer,9000.00,JPY
   ```

2. Commit and push → the **Data pipeline** workflow triggers on `data/**`.
3. Watch it in the Actions tab: it installs pandas/flask, runs the script,
   then commits the refreshed `orders.db` back to the repo.
4. Locally: `git pull` (the database file itself is updated), restart Flask and
   the dashboard shows the new orders and the updated regional averages.
