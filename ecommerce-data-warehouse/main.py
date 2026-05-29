"""
Main ETL Pipeline for Olist Brazilian E-commerce Dataset
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from config.config import setup_logging, get_logger
from scripts.extract import extract_bronze_layer
from scripts.transform import transform_silver_layer
from scripts.load import load_to_mysql
from scripts.scd2 import merge_scd2_dimensions

# Setup logging
logger = setup_logging()

def validate_environment():
    """Validate environment setup"""
    logger.info("Validating environment...")
    
    # Check for Olist data files
    required_files = [
        'data/raw/olist_customers_dataset.csv',
        'data/raw/olist_orders_dataset.csv',
        'data/raw/olist_products_dataset.csv'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        logger.error("Missing required Olist data files:")
        for f in missing_files:
            logger.error(f"  - {f}")
        logger.error("\nPlease download dataset from:")
        logger.error("https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        return False
    
    logger.info("✅ Environment validation passed")
    return True

def run_full_pipeline():
    """Run complete ETL pipeline"""
    logger.info("🚀 Starting full ETL pipeline for Olist dataset")
    
    steps = [
        ("Extract (Bronze)", extract_bronze_layer),
        ("Transform (Silver)", transform_silver_layer),
        ("Load to MySQL", load_to_mysql),
        ("SCD2 Merge", merge_scd2_dimensions)
    ]
    
    for step_name, step_func in steps:
        logger.info(f"\n{'='*60}")
        logger.info(f"Executing: {step_name}")
        logger.info(f"{'='*60}")
        
        start_time = datetime.now()
        success = step_func()
        duration = (datetime.now() - start_time).total_seconds()
        
        if success:
            logger.info(f"✅ {step_name} completed in {duration:.2f} seconds")
        else:
            logger.error(f"❌ {step_name} failed")
            return False
    
    logger.info("\n" + "="*60)
    logger.info("🎉 ETL PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("="*60)
    return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Olist ETL Pipeline')
    parser.add_argument('--stage', choices=['all', 'extract', 'transform', 'load', 'scd2'],
                       default='all', help='Pipeline stage to run')
    
    args = parser.parse_args()
    
    if not validate_environment():
        sys.exit(1)
    
    if args.stage == 'all':
        success = run_full_pipeline()
    elif args.stage == 'extract':
        success = extract_bronze_layer()
    elif args.stage == 'transform':
        success = transform_silver_layer()
    elif args.stage == 'load':
        success = load_to_mysql()
    elif args.stage == 'scd2':
        success = merge_scd2_dimensions()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()