# Architecture Overview

This document describes the local ecommerce data warehouse from source ingestion through analytics consumption.

## 1. End-to-End Architecture

```text
Source Systems
  -> Raw Inputs
  -> Bronze Layer
  -> Silver Layer
  -> Gold Layer
  -> MySQL Warehouse
  -> SQL Analytics and Dashboards
```

### Purpose of Each Layer

**Source systems**
- External ecommerce exports, CSV files, JSON feeds, or database extracts.
- Treated as immutable inputs.

**Raw inputs (`data/raw`)**
- Local copy of source extracts before transformation.
- Useful for reproducibility and debugging.

**Bronze layer (`data/bronze`)**
- Stores ingested data with minimal changes.
- Preserves original structure and raw history.
- Supports reprocessing if downstream logic changes.

**Silver layer (`data/silver`)**
- Stores cleaned, deduplicated, typed, and validated data.
- Used as the trusted staging layer for warehouse loading.

**Gold layer (`data/gold`)**
- Stores curated business entities prepared for analytics.
- Contains dimension-ready and fact-ready datasets.
- Applies business rules and SCD Type 2 preparation.

**Warehouse layer (MySQL)**
- Stores final dimensional model tables.
- Acts as the persistent analytics system of record.
- Supports joins, aggregations, and reporting queries.

**Analytics layer**
- SQL scripts, notebook analysis, dashboard logic, and KPI outputs.
- Consumes warehouse tables only.

## 2. Data Flow

1. Source files are copied or read from `data/raw`.
2. `scripts/extract.py` loads source data and writes Bronze Parquet files.
3. `scripts/transform.py` reads Bronze data, cleans it, and writes Silver Parquet files.
4. `scripts/scd2.py` compares Silver data with existing dimension history.
5. `scripts/load.py` loads fact and dimension tables into MySQL.
6. `sql/analytics_queries.sql` queries the warehouse for business analysis.
7. `notebooks/exploration.ipynb` is used for profiling, validation, and experimentation.

## 3. Persistent vs Transient Artifacts

### Transient artifacts
- Python DataFrames in memory.
- Notebook variables.
- Temporary query results.

### Persistent artifacts
- Files under `data/raw`, `data/bronze`, `data/silver`, and `data/gold`.
- MySQL warehouse tables.
- SQL scripts in `sql/`.
- Logs in `logs/`.
- Documentation in `README.md` and `docs/`.

## 4. File and Folder Responsibilities

### Root files
- `main.py`: entry point that orchestrates the full pipeline.
- `README.md`: primary project documentation.
- `.gitignore`: excludes local and generated artifacts.
- `requirements.txt`: Python dependencies.
- `.env.example`: example environment variables.

### `config/`
- `config/config.py`: centralized configuration, paths, logging, and MySQL connection settings.

### `scripts/`
- `scripts/extract.py`: reads source data and writes Bronze files.
- `scripts/transform.py`: cleans and validates Bronze data and writes Silver files.
- `scripts/scd2.py`: handles historical versioning for dimensions.
- `scripts/load.py`: loads curated data into MySQL.
- `scripts/etl_pipeline.py`: orchestrates the pipeline stages in order.

### `sql/`
- `sql/schema_mysql.sql`: defines warehouse tables, keys, indexes, and views.
- `sql/analytics_queries.sql`: contains reusable business queries.

### `notebooks/`
- `notebooks/exploration.ipynb`: interactive profiling and validation notebook.

### `data/`
- `data/raw/`: source extracts.
- `data/bronze/`: raw persisted files.
- `data/silver/`: cleaned persisted files.
- `data/gold/`: curated persisted files.

### Supporting folders
- `logs/`: runtime logs.
- `dashboards/`: future BI assets.
- `tests/`: automated tests.
- `docs/`: architecture and design documentation.

## 5. Fact and Dimension Flow

### Fact table flow
- Raw orders are cleaned in Silver.
- The final transaction table becomes `fact_orders` in MySQL.
- The grain is one row per order line item.

### Dimension table flow
- Customers and products are cleaned in Silver.
- `scripts/scd2.py` detects changes and preserves history.
- The final dimensions become `dim_customer`, `dim_product`, `dim_seller`, `dim_date`, and `dim_geolocation`.
- `dim_date` is generated as a conformed calendar dimension.
- `dim_seller` and `dim_geolocation` provide reference and geographic support.

## 6. SCD Type 2 Strategy

SCD Type 2 is used for dimensions that change over time, especially customers and products.

Required columns:
- `effective_date`: when the version starts.
- `end_date`: when the version stops being current.
- `is_current`: whether the record is active.

Behavior:
- If a tracked attribute changes, the old row is closed with an `end_date`.
- A new row is inserted with a new `effective_date`.
- Historical reporting remains accurate because old versions are preserved.

## 7. Warehouse Tables

Core tables:
- `fact_orders`
- `dim_customer`
- `dim_product`
- `dim_seller`
- `dim_date`
- `dim_geolocation`

Optional supporting views:
- Current customer view.
- Current product view.
- Order detail view.
- Customer lifetime value view.
- Product performance view.

## 8. Practical Implementation Rule

Keep the pipeline order strict:
1. Extract
2. Bronze write
3. Clean and validate
4. Silver write
5. Apply SCD Type 2
6. Load warehouse tables
7. Run analytics queries

This keeps the project reproducible, easy to debug, and realistic for a junior portfolio.
