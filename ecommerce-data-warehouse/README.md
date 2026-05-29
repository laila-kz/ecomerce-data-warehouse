# Ecommerce Analytics Data Warehouse

Local junior-friendly data engineering project using Python, pandas, MySQL, SQL, dimensional modeling, Bronze/Silver/Gold layers, ETL, and SCD Type 2.

## Architecture

```text
Source Systems
  -> data/raw
  -> Bronze Layer
  -> Silver Layer
  -> Gold Layer
      -> MySQL Warehouse
  -> SQL Analytics and Dashboards
```

### Layer Responsibilities

**Source layer**
- Original ecommerce extracts such as CSV, JSON, or database dumps.
- Transient input only.
- Example files: data/raw/customers.csv, data/raw/products.csv, data/raw/orders.csv.

**Bronze layer**
- Minimal-transformation landing zone.
- Persistent raw history for traceability and reprocessing.
- Example files: data/bronze/customers.parquet, data/bronze/products.parquet, data/bronze/orders.parquet.

**Silver layer**
- Cleaned, standardized, typed, and deduplicated data.
- Persistent trusted staging layer.
- Example files: data/silver/customers.parquet, data/silver/products.parquet, data/silver/orders.parquet.

**Gold layer**
- Curated analytics-ready data.
- Persistent curated layer used for loading dimensions and facts.
- Example files: data/gold/dim_customer.parquet, data/gold/dim_product.parquet.

**Warehouse layer**
- MySQL fact and dimension tables.
- Persistent system of record for analytics.
- Example tables: fact_orders, dim_customer, dim_product, dim_seller, dim_date, dim_geolocation.

**Analytics layer**
- SQL queries, notebooks, and dashboard-ready outputs.
- Mostly read-only consumption layer.
- Example files: sql/analytics_queries.sql, notebooks/exploration.ipynb, dashboards/.

### Transient vs Persistent

**Transient**
- In-memory DataFrames.
- Notebook scratch variables.
- Temporary query results.

**Persistent**
- data/raw, data/bronze, data/silver, data/gold.
- MySQL warehouse tables.
- SQL scripts, logs, notebooks, and documentation.

### File and Table Map

- main.py: pipeline entry point.
- config/config.py: environment variables, paths, database connection settings.
- scripts/extract.py: reads source data and writes Bronze files.
- scripts/transform.py: cleans Bronze data and writes Silver files.
- scripts/scd2.py: applies Slowly Changing Dimension Type 2 logic.
- scripts/load.py: loads fact and dimension data into MySQL.
- scripts/etl_pipeline.py: runs the stages in order.
- sql/schema_mysql.sql: warehouse DDL, keys, and views.
- sql/analytics_queries.sql: business queries and KPI templates.
- notebooks/exploration.ipynb: profiling, validation, and analysis.

### Architecture Diagram

```text
[Source Systems]
      |
      v
[data/raw] -> extract.py -> [data/bronze]
      |
      v
transform.py -> [data/silver]
      |
      v
scd2.py + load.py -> [data/gold] -> MySQL Warehouse
      |
      v
sql/analytics_queries.sql -> Dashboards / Reporting
```

### Why This Design Works

- It keeps raw history available for debugging and reprocessing.
- It separates cleansing from loading so each step is testable.
- It supports a star schema for simple analytics queries.
- It preserves history with SCD Type 2 where business attributes change over time.
- It stays realistic for a strong junior portfolio without overengineering.
