"""
Transform module for Olist dataset
Cleans and prepares data for dimensional modeling
"""

import pandas as pd
import numpy as np
import logging
import re
from pathlib import Path
from typing import Dict, Tuple
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.config import BRONZE_DIR, SILVER_DIR, get_logger

logger = get_logger(__name__)

class OlistTransformer:
    """Transform Olist data from bronze to silver layer"""
    
    def __init__(self):
        self.bronze_data = {}
        
    def load_latest_bronze(self) -> Dict[str, pd.DataFrame]:
        """Load the most recent bronze files"""
        bronze_files = list(BRONZE_DIR.glob("bronze_*.parquet"))
        
        # Group by file type and take latest
        file_groups = {}
        for file_path in bronze_files:
            # Extract file key from bronze_{file_key}_{timestamp}.parquet
            match = re.match(r"^bronze_(.+)_\d{8}_\d{6}$", file_path.stem)
            if not match:
                logger.warning(f"Skipping unrecognized bronze file name: {file_path.name}")
                continue

            file_key = match.group(1)
            if file_key not in file_groups:
                file_groups[file_key] = []
            file_groups[file_key].append(file_path)
        
        # Take latest file for each type
        for key, files in file_groups.items():
            latest = max(files, key=lambda p: p.stat().st_mtime)
            self.bronze_data[key] = pd.read_parquet(latest)
            logger.info(f"Loaded bronze data: {key} ({len(self.bronze_data[key]):,} rows)")
        
        return self.bronze_data
    
    def transform_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean orders table"""
        logger.info("Transforming orders data")
        
        # Convert date columns
        date_columns = ['order_purchase_timestamp', 'order_approved_at', 
                       'order_delivered_carrier_date', 'order_delivered_customer_date',
                       'order_estimated_delivery_date']
        
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Create date dimension keys
        df['order_date_key'] = df['order_purchase_timestamp'].dt.strftime('%Y%m%d').fillna('99991231').astype(int)
        
        # Handle missing values
        df['order_status'] = df['order_status'].fillna('unknown')
        
        # Add derived columns
        df['delivery_days'] = (df['order_delivered_customer_date'] - df['order_purchase_timestamp']).dt.days
        df['delivery_delay'] = (df['order_delivered_customer_date'] - df['order_estimated_delivery_date']).dt.days
        
        # Filter out test orders (convert to string first to handle numeric IDs)
        df = df[~df['customer_id'].astype(str).str.contains('test', case=False, na=False)]
        
        logger.info(f"Orders transformed: {len(df):,} rows")
        return df
    
    def transform_customers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean customers table and prepare for SCD2"""
        logger.info("Transforming customers data")
        
        # Clean customer data
        df['customer_city'] = df['customer_city'].str.title().str.strip()
        df['customer_state'] = df['customer_state'].str.upper().str.strip()
        
        # Add SCD2 columns
        df['valid_from'] = pd.Timestamp.now().normalize()
        df['valid_to'] = pd.NaT
        df['is_current'] = True
        df['version'] = 1
        
        logger.info(f"Customers transformed: {len(df):,} rows")
        return df
    
    def transform_products(self, df: pd.DataFrame, category_df: pd.DataFrame) -> pd.DataFrame:
        """Transform products with category translation"""
        logger.info("Transforming products data")
        
        # Merge with category translation
        if not category_df.empty and 'product_category_name' in df.columns and 'product_category_name_english' in category_df.columns:
            df = df.merge(category_df, on='product_category_name', how='left')
            df['product_category_name_english'] = df['product_category_name_english'].fillna('Unknown')
        elif 'product_category_name_english' not in df.columns:
            df['product_category_name_english'] = 'Unknown'
        
        # Clean dimensions
        df['product_weight_g'] = df['product_weight_g'].fillna(df['product_weight_g'].median())
        df['product_length_cm'] = df['product_length_cm'].fillna(0)
        df['product_height_cm'] = df['product_height_cm'].fillna(0)
        df['product_width_cm'] = df['product_width_cm'].fillna(0)
        
        # Calculate product volume
        df['product_volume_cm3'] = df['product_length_cm'] * df['product_height_cm'] * df['product_width_cm']
        
        logger.info(f"Products transformed: {len(df):,} rows")
        return df
    
    def transform_order_items(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean order items"""
        logger.info("Transforming order items data")
        
        # Convert to numeric FIRST before calculations
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['freight_value'] = pd.to_numeric(df['freight_value'], errors='coerce')
        
        # Calculate total price per item
        df['total_price'] = df['price'] + df['freight_value']
        
        logger.info(f"Order items transformed: {len(df):,} rows")
        return df
    
    def transform_payments(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate payments per order"""
        logger.info("Transforming payments data")
        
        # Group by order_id to get total payment value
        payment_summary = df.groupby('order_id').agg({
            'payment_value': 'sum',
            'payment_type': lambda x: ', '.join(x.unique()),
            'payment_installments': 'max'
        }).reset_index()
        
        payment_summary.columns = ['order_id', 'total_payment_value', 'payment_types', 'max_installments']
        
        logger.info(f"Payments aggregated: {len(payment_summary):,} orders")
        return payment_summary
    
    def create_fact_orders(self, orders_df, items_df, payments_df) -> pd.DataFrame:
        """Create fact_orders table by joining multiple sources"""
        logger.info("Creating fact_orders table")
        
        # Aggregate items per order
        order_items_agg = items_df.groupby('order_id').agg({
            'order_item_id': 'count',
            'price': 'sum',
            'freight_value': 'sum',
            'product_id': 'count'
        }).reset_index()
        
        order_items_agg.columns = ['order_id', 'item_count', 'total_price', 'total_freight', 'product_count']
        
        # Merge with orders
        fact = orders_df.merge(order_items_agg, on='order_id', how='inner')
        
        # Merge with payments
        fact = fact.merge(payments_df, on='order_id', how='left')
        
        # Calculate derived metrics
        fact['total_order_value'] = fact['total_price'] + fact['total_freight']
        fact['is_late_delivery'] = fact['delivery_delay'] > 0
        
        # Fill missing values
        fact['total_payment_value'] = fact['total_payment_value'].fillna(fact['total_order_value'])
        
        logger.info(f"Fact orders created: {len(fact):,} rows")
        return fact
    
    def save_silver_layer(self, data_dict: Dict[str, pd.DataFrame]) -> bool:
        """Save all transformed data to silver layer"""
        for key, df in data_dict.items():
            silver_file = SILVER_DIR / f"silver_{key}.parquet"
            df.to_parquet(silver_file, index=False)
            logger.info(f"Saved silver layer: {silver_file.name}")
        return True

def transform_silver_layer() -> bool:
    """Main transformation orchestration"""
    logger.info("=" * 60)
    logger.info("SILVER LAYER TRANSFORMATION - Olist Dataset")
    logger.info("=" * 60)
    
    transformer = OlistTransformer()
    
    # Load bronze data
    bronze_data = transformer.load_latest_bronze()
    
    if not bronze_data:
        logger.error("No bronze data found")
        return False
    
    silver_data = {}
    
    # Transform each table
    if 'orders' in bronze_data:
        silver_data['orders'] = transformer.transform_orders(bronze_data['orders'])
    
    if 'customers' in bronze_data:
        silver_data['customers'] = transformer.transform_customers(bronze_data['customers'])
    
    if 'products' in bronze_data:
        category_df = bronze_data.get('product_category', pd.DataFrame())
        silver_data['products'] = transformer.transform_products(bronze_data['products'], category_df)
    
    if 'order_items' in bronze_data:
        silver_data['order_items'] = transformer.transform_order_items(bronze_data['order_items'])
    
    if 'order_payments' in bronze_data:
        silver_data['payments_summary'] = transformer.transform_payments(bronze_data['order_payments'])
    
    if 'sellers' in bronze_data:
        silver_data['sellers'] = bronze_data['sellers'].copy()
        logger.info(f"Sellers transformed: {len(silver_data['sellers']):,} rows")
    
    # Create fact table
    if all(k in silver_data for k in ['orders', 'order_items', 'payments_summary']):
        silver_data['fact_orders'] = transformer.create_fact_orders(
            silver_data['orders'],
            silver_data['order_items'],
            silver_data['payments_summary']
        )
    
    # Save to silver
    transformer.save_silver_layer(silver_data)
    
    logger.info("\n📊 Silver Layer Summary:")
    for key, df in silver_data.items():
        logger.info(f"  {key}: {len(df):,} records")
    
    return True

if __name__ == "__main__":
    transform_silver_layer()