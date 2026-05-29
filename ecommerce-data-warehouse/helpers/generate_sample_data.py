"""
Helper script to download Olist dataset
Since the dataset is 126MB, this provides instructions
"""

import os
import subprocess
import sys
from pathlib import Path
import logging

sys.path.append(str(Path(__file__).parent.parent))
from config.config import RAW_DIR, get_logger

logger = get_logger(__name__)

def download_olist_dataset():
    """
    Instructions to download Olist dataset from Kaggle
    """
    print("\n" + "="*70)
    print("📦 OLIST DATASET DOWNLOAD INSTRUCTIONS")
    print("="*70)
    
    print("\nOption 1: Download via Kaggle API (Recommended)")
    print("-" * 50)
    print("1. Install Kaggle API:")
    print("   pip install kaggle")
    print("\n2. Get Kaggle API credentials:")
    print("   - Go to https://www.kaggle.com/settings/account")
    print("   - Create API token (downloads kaggle.json)")
    print("   - Place kaggle.json in ~/.kaggle/")
    print("\n3. Download dataset:")
    print(f"   kaggle datasets download olistbr/brazilian-ecommerce -p {RAW_DIR}")
    print("   cd data/raw/")
    print("   unzip brazilian-ecommerce.zip")
    
    print("\nOption 2: Manual Download")
    print("-" * 50)
    print("1. Go to: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
    print("2. Click 'Download' button")
    print(f"3. Extract all CSV files to: {RAW_DIR}/")
    print("4. Files should include:")
    for file in ['olist_customers_dataset.csv', 'olist_orders_dataset.csv', 
                 'olist_products_dataset.csv', 'olist_order_items_dataset.csv',
                 'olist_order_payments_dataset.csv', 'olist_sellers_dataset.csv']:
        print(f"   - {file}")
    
    print("\nOption 3: Use sample data (for testing)")
    print("-" * 50)
    print("Run: python helpers/create_sample_olist_data.py")
    print("This creates small sample files for testing the pipeline")
    
    print("\n" + "="*70)

def check_existing_files():
    """Check if Olist files already exist"""
    required_files = [
        'olist_customers_dataset.csv',
        'olist_orders_dataset.csv',
        'olist_products_dataset.csv',
        'olist_order_items_dataset.csv'
    ]
    
    existing_files = []
    missing_files = []
    
    for file in required_files:
        file_path = RAW_DIR / file
        if file_path.exists():
            existing_files.append(file)
        else:
            missing_files.append(file)
    
    if existing_files:
        print("\n✅ Found existing files:")
        for f in existing_files:
            size = (RAW_DIR / f).stat().st_size / 1024 / 1024
            print(f"   - {f} ({size:.2f} MB)")
    
    if missing_files:
        print("\n❌ Missing files:")
        for f in missing_files:
            print(f"   - {f}")
    
    return len(existing_files) > 0

if __name__ == "__main__":
    print("\n📊 Brazilian E-Commerce Dataset Setup\n")
    
    if check_existing_files():
        print("\n✅ Dataset already present! Ready to run ETL pipeline.")
        print("\nNext steps:")
        print("1. Run: python main.py --stage extract")
        print("2. Run: python main.py --stage transform")
        print("3. Run: python main.py --stage load")
    else:
        download_olist_dataset()