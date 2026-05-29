"""
Configuration for Brazilian E-commerce Olist Dataset
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
RAW_DIR = DATA_DIR / 'raw'
BRONZE_DIR = DATA_DIR / 'bronze'
SILVER_DIR = DATA_DIR / 'silver'
GOLD_DIR = DATA_DIR / 'gold'
LOGS_DIR = PROJECT_ROOT / 'logs'

# Create directories
for dir_path in [RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Olist specific file paths
OLIST_FILES = {
    'customers': RAW_DIR / 'olist_customers_dataset.csv',
    'geolocation': RAW_DIR / 'olist_geolocation_dataset.csv',
    'order_items': RAW_DIR / 'olist_order_items_dataset.csv',
    'order_payments': RAW_DIR / 'olist_order_payments_dataset.csv',
    'order_reviews': RAW_DIR / 'olist_order_reviews_dataset.csv',
    'orders': RAW_DIR / 'olist_orders_dataset.csv',
    'products': RAW_DIR / 'olist_products_dataset.csv',
    'sellers': RAW_DIR / 'olist_sellers_dataset.csv',
    'product_category': RAW_DIR / 'product_category_name_translation.csv'
}

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ecommerce_dw'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

def get_db_connection_string():
    """Return SQLAlchemy connection string"""
    return f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"

# ETL Configuration
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 5000))

def setup_logging():
    """Setup logging configuration"""
    log_file = LOGS_DIR / f'etl_{datetime.now().strftime("%Y%m%d")}.log'

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    
    logging.basicConfig(
        level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger

def get_logger(name):
    """Get a logger instance"""
    return logging.getLogger(name)