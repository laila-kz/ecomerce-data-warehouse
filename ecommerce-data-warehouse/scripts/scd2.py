"""
SCD Type 2 handling for the Olist customer dimension.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(str(Path(__file__).parent.parent))
from config.config import SILVER_DIR, get_db_connection_string, get_logger

logger = get_logger(__name__)

TRACKED_COLUMNS = [
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
]


def _get_engine():
    return create_engine(get_db_connection_string(), future=True)


def _load_customer_snapshot() -> pd.DataFrame:
    file_path = SILVER_DIR / "silver_customers.parquet"
    if not file_path.exists():
        raise FileNotFoundError(f"Missing silver customer snapshot: {file_path}")

    snapshot = pd.read_parquet(file_path).copy()
    snapshot = snapshot.drop_duplicates(subset=["customer_id"], keep="last")
    for column in TRACKED_COLUMNS:
        if column in snapshot.columns:
            snapshot[column] = snapshot[column].fillna("").astype(str).str.strip()
    return snapshot


def _row_changed(snapshot_row: dict, current_row: dict) -> bool:
    for column in TRACKED_COLUMNS:
        left_value = str(snapshot_row.get(column, "")).strip()
        right_value = str(current_row.get(column, "")).strip()
        if left_value != right_value:
            return True
    return False


def _expire_customer_rows(connection, customer_keys: list[int]) -> None:
    if not customer_keys:
        return

    key_placeholders = ", ".join(str(key) for key in customer_keys)
    connection.exec_driver_sql(
        f"""
        UPDATE dim_customer
        SET valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY),
            is_current = 0
        WHERE customer_key IN ({key_placeholders})
        """
    )


def _insert_customer_rows(connection, rows: list[dict]) -> None:
    if not rows:
        return

    dataframe = pd.DataFrame(rows)
    dataframe.to_sql("dim_customer", con=connection, if_exists="append", index=False, method="multi", chunksize=1000)


def merge_scd2_dimensions() -> bool:
    """Merge the current customer snapshot into the SCD2 dimension table."""
    logger.info("=" * 60)
    logger.info("SCD2 MERGE - Customer Dimension")
    logger.info("=" * 60)

    try:
        snapshot = _load_customer_snapshot()
        engine = _get_engine()

        with engine.begin() as connection:
            try:
                current_rows = pd.read_sql(
                    text(
                        """
                        SELECT customer_key, customer_id, customer_unique_id,
                               customer_zip_code_prefix, customer_city, customer_state, version
                        FROM dim_customer
                        WHERE is_current = 1
                        """
                    ),
                    connection,
                )
            except Exception:
                current_rows = pd.DataFrame()

            if current_rows.empty:
                logger.info("No existing customer dimension rows found. Loading snapshot as version 1.")
                initial_rows = snapshot.copy()
                initial_rows["valid_from"] = pd.Timestamp.now().normalize().date()
                initial_rows["valid_to"] = pd.NA
                initial_rows["is_current"] = 1
                initial_rows["version"] = 1
                initial_rows["created_at"] = pd.Timestamp.now()
                _insert_customer_rows(
                    connection,
                    initial_rows[
                        [
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
                    ].to_dict("records"),
                )
                logger.info("Loaded %s customer rows.", f"{len(initial_rows):,}")
                return True

            current_lookup = current_rows.set_index("customer_id").to_dict("index")
            expire_keys: list[int] = []
            new_rows: list[dict] = []
            changed_count = 0
            inserted_count = 0

            today = pd.Timestamp.now().normalize().date()
            now = pd.Timestamp.now()

            for snapshot_row in snapshot.to_dict("records"):
                customer_id = snapshot_row["customer_id"]
                current_row = current_lookup.get(customer_id)

                if current_row is None:
                    inserted_count += 1
                    new_rows.append(
                        {
                            "customer_id": snapshot_row["customer_id"],
                            "customer_unique_id": snapshot_row.get("customer_unique_id"),
                            "customer_zip_code_prefix": snapshot_row.get("customer_zip_code_prefix"),
                            "customer_city": snapshot_row.get("customer_city"),
                            "customer_state": snapshot_row.get("customer_state"),
                            "valid_from": today,
                            "valid_to": pd.NA,
                            "is_current": 1,
                            "version": 1,
                            "created_at": now,
                        }
                    )
                    continue

                if _row_changed(snapshot_row, current_row):
                    changed_count += 1
                    expire_keys.append(int(current_row["customer_key"]))
                    new_rows.append(
                        {
                            "customer_id": snapshot_row["customer_id"],
                            "customer_unique_id": snapshot_row.get("customer_unique_id"),
                            "customer_zip_code_prefix": snapshot_row.get("customer_zip_code_prefix"),
                            "customer_city": snapshot_row.get("customer_city"),
                            "customer_state": snapshot_row.get("customer_state"),
                            "valid_from": today,
                            "valid_to": pd.NA,
                            "is_current": 1,
                            "version": int(current_row["version"]) + 1,
                            "created_at": now,
                        }
                    )

            _expire_customer_rows(connection, expire_keys)
            _insert_customer_rows(connection, new_rows)

        logger.info("SCD2 merge complete: %s updated, %s inserted.", f"{changed_count:,}", f"{inserted_count:,}")
        return True

    except Exception as exc:
        logger.error("SCD2 merge failed: %s", exc)
        return False


if __name__ == "__main__":
    merge_scd2_dimensions()