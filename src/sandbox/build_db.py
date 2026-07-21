import duckdb
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "olist_raw")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sandbox.duckdb")

TABLES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = duckdb.connect(DB_PATH)
    for table_name, csv_file in TABLES.items():
        csv_path = os.path.join(RAW_DIR, csv_file)
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_path}', header=true)")
        count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  loaded {table_name:20s} {count:>8,} rows")
    con.close()
    print(f"\nSandbox built at {DB_PATH}")

def get_readonly_connection():
    return duckdb.connect(DB_PATH, read_only=True)

if __name__ == "__main__":
    build()
