"""
Load module for Olist dataset.
Loads curated silver data into a MySQL star schema and writes gold snapshots.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(str(Path(__file__).parent.parent))
from config.config import DB_CONFIG, GOLD_DIR, RAW_DIR, SILVER_DIR, get_db_connection_string, get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema_mysql.sql"


def _mysql_server_connection_string() -> str:
    return (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/?charset=utf8mb4"
    )


def _get_engine(use_database: bool = True):
    connection_string = get_db_connection_string() if use_database else _mysql_server_connection_string()
    return create_engine(connection_string, future=True)


def _execute_sql_script(engine, script_path: Path) -> None:
    raw_script = script_path.read_text(encoding="utf-8")
    cleaned_lines = []

    for line in raw_script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped.startswith("#"):
            continue
        line_without_inline_comment = re.split(r"\s+--|\s+#", line, maxsplit=1)[0]
        if line_without_inline_comment.strip():
            cleaned_lines.append(line_without_inline_comment)

    statements = [statement.strip() for statement in "\n".join(cleaned_lines).split(";") if statement.strip()]

    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement.replace("%", "%%"))


def _load_parquet(name: str) -> pd.DataFrame:
    file_path = SILVER_DIR / f"silver_{name}.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Missing silver layer file: {file_path}")
    return pd.read_parquet(file_path)


def _load_raw_csv(name: str) -> pd.DataFrame:
    file_path = RAW_DIR / name
    if not file_path.exists():
        raise FileNotFoundError(f"Missing raw file: {file_path}")
    return pd.read_csv(file_path)


def _prepare_customers(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy().drop_duplicates(subset=["customer_id"], keep="last")
    prepared["valid_from"] = pd.Timestamp.now().normalize().date()
    prepared["valid_to"] = pd.NA
    prepared["is_current"] = 1
    prepared["version"] = 1
    prepared["created_at"] = pd.Timestamp.now()
    columns = [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
        "valid_from",
        "valid_to",
        "is_current",
        "version",
        "created_at",
    ]
    return prepared[columns]


def _prepare_products(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy().drop_duplicates(subset=["product_id"], keep="last")
    prepared["created_at"] = pd.Timestamp.now()
    columns = [
        "product_id",
        "product_category_name",
        "product_category_name_english",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_volume_cm3",
        "created_at",
    ]
    return prepared[columns]


def _prepare_sellers(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy().drop_duplicates(subset=["seller_id"], keep="last")
    prepared["created_at"] = pd.Timestamp.now()
    columns = ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state", "created_at"]
    return prepared[columns]


def _prepare_geolocation() -> pd.DataFrame:
    geolocation = _load_raw_csv("olist_geolocation_dataset.csv").copy()
    geolocation = geolocation.rename(
        columns={
            "geolocation_zip_code_prefix": "zip_code_prefix",
            "geolocation_lat": "geolocation_lat",
            "geolocation_lng": "geolocation_lng",
            "geolocation_city": "geolocation_city",
            "geolocation_state": "geolocation_state",
        }
    )
    return geolocation[
        ["zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"]
    ]


def _prepare_reviews() -> pd.DataFrame:
    reviews = _load_raw_csv("olist_order_reviews_dataset.csv")
    return (
        reviews.groupby("order_id", as_index=False)
        .agg({"review_score": "max"})
    )


def _load_table(engine, table_name: str, dataframe: pd.DataFrame) -> None:
    dataframe.to_sql(table_name, con=engine, if_exists="append", index=False, method="multi", chunksize=1000)
    logger.info("Loaded %s rows into %s", f"{len(dataframe):,}", table_name)


def _save_gold_snapshot(name: str, dataframe: pd.DataFrame) -> None:
    output_file = GOLD_DIR / f"gold_{name}.parquet"
    dataframe.to_parquet(output_file, index=False)
    logger.info("Saved gold snapshot: %s", output_file.name)


def _build_fact_orders(engine) -> pd.DataFrame:
    orders = _load_parquet("orders").copy()
    items = _load_parquet("order_items").copy()
    payments = _load_parquet("payments_summary").copy()
    customers = _load_parquet("customers").copy()
    products = _load_parquet("products").copy()
    sellers = _load_parquet("sellers").copy()
    reviews = _prepare_reviews()

    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
    orders["order_delivered_customer_date"] = pd.to_datetime(orders["order_delivered_customer_date"], errors="coerce")
    orders["order_estimated_delivery_date"] = pd.to_datetime(orders["order_estimated_delivery_date"], errors="coerce")

    fact = items.merge(
        orders[
            [
                "order_id",
                "customer_id",
                "order_status",
                "order_purchase_timestamp",
                "order_delivered_customer_date",
                "order_estimated_delivery_date",
            ]
        ],
        on="order_id",
        how="inner",
    )
    fact = fact.merge(payments, on="order_id", how="left")
    fact = fact.merge(reviews, on="order_id", how="left")

    customer_map = pd.read_sql(text("SELECT customer_key, customer_id FROM dim_customer"), engine).set_index("customer_id")[
        "customer_key"
    ]
    product_map = pd.read_sql(text("SELECT product_key, product_id FROM dim_product"), engine).set_index("product_id")[
        "product_key"
    ]
    seller_map = pd.read_sql(text("SELECT seller_key, seller_id FROM dim_seller"), engine).set_index("seller_id")[
        "seller_key"
    ]

    fact["customer_key"] = fact["customer_id"].map(customer_map)
    fact["product_key"] = fact["product_id"].map(product_map)
    fact["seller_key"] = fact["seller_id"].map(seller_map)
    fact["date_key"] = pd.to_datetime(fact["order_purchase_timestamp"], errors="coerce").dt.strftime("%Y%m%d")
    fact["date_key"] = pd.to_numeric(fact["date_key"], errors="coerce").astype("Int64")

    fact["price"] = pd.to_numeric(fact["price"], errors="coerce")
    fact["freight_value"] = pd.to_numeric(fact["freight_value"], errors="coerce")
    fact["total_item_value"] = fact["price"] + fact["freight_value"]
    fact["delivery_days"] = (fact["order_delivered_customer_date"] - fact["order_purchase_timestamp"]).dt.days
    fact["delivery_delay"] = (fact["order_delivered_customer_date"] - fact["order_estimated_delivery_date"]).dt.days
    fact["is_late_delivery"] = fact["delivery_delay"].fillna(0) > 0
    fact["payment_type"] = fact["payment_types"]
    fact["payment_installments"] = fact["max_installments"]
    fact["payment_value"] = fact["total_payment_value"]
    fact["order_delivered_timestamp"] = fact["order_delivered_customer_date"]
    fact["created_at"] = pd.Timestamp.now()

    fact = fact.dropna(subset=["customer_key", "product_key", "seller_key", "date_key"])

    columns = [
        "order_id",
        "order_item_id",
        "customer_key",
        "product_key",
        "seller_key",
        "date_key",
        "price",
        "freight_value",
        "total_item_value",
        "order_purchase_timestamp",
        "order_delivered_timestamp",
        "delivery_days",
        "delivery_delay",
        "is_late_delivery",
        "review_score",
        "payment_type",
        "payment_installments",
        "payment_value",
        "order_status",
        "created_at",
    ]
    return fact[columns]


def load_to_mysql() -> bool:
    """Load silver data into the MySQL warehouse."""
    logger.info("=" * 60)
    logger.info("MYSQL WAREHOUSE LOAD - Olist Dataset")
    logger.info("=" * 60)

    try:
        server_engine = _get_engine(use_database=False)
        with server_engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")

        db_engine = _get_engine(use_database=True)
        _execute_sql_script(db_engine, SCHEMA_FILE)

        customers = _load_parquet("customers")
        products = _load_parquet("products")
        sellers = _load_parquet("sellers")

        dim_customer = _prepare_customers(customers)
        dim_product = _prepare_products(products)
        dim_seller = _prepare_sellers(sellers)
        dim_geolocation = _prepare_geolocation()

        with db_engine.begin() as conn:
            _load_table(conn, "dim_customer", dim_customer)
            _load_table(conn, "dim_product", dim_product)
            _load_table(conn, "dim_seller", dim_seller)
            _load_table(conn, "dim_geolocation", dim_geolocation)

        fact_orders = _build_fact_orders(db_engine)

        with db_engine.begin() as conn:
            _load_table(conn, "fact_orders", fact_orders)

        _save_gold_snapshot("dim_customer", dim_customer)
        _save_gold_snapshot("dim_product", dim_product)
        _save_gold_snapshot("dim_seller", dim_seller)
        _save_gold_snapshot("dim_geolocation", dim_geolocation)
        _save_gold_snapshot("fact_orders", fact_orders)

        logger.info("\n📊 MySQL Load Summary:")
        logger.info("  dim_customer: %s records", f"{len(dim_customer):,}")
        logger.info("  dim_product: %s records", f"{len(dim_product):,}")
        logger.info("  dim_seller: %s records", f"{len(dim_seller):,}")
        logger.info("  dim_geolocation: %s records", f"{len(dim_geolocation):,}")
        logger.info("  fact_orders: %s records", f"{len(fact_orders):,}")

        return True

    except Exception as exc:
        logger.error("Failed to load MySQL warehouse: %s", exc)
        return False
if __name__ == "__main__":
    load_to_mysql()