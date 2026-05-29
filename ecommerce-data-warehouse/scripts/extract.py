"""
Extract module for Olist Brazilian E-commerce dataset
Reads all 9 CSV files and saves to bronze layer
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.config import OLIST_FILES, BRONZE_DIR, get_logger

logger = get_logger(__name__)

class OlistExtractor:
    """Extractor for Olist dataset files"""
    
    def __init__(self):
        self.extracted_data = {}
        
    def extract_all_files(self) -> Dict[str, pd.DataFrame]:
        """Extract all Olist CSV files"""
        logger.info("Starting extraction of Olist dataset")
        
        for file_key, file_path in OLIST_FILES.items():
            if file_path.exists():
                logger.info(f"Extracting {file_key} from {file_path.name}")
                try:
                    df = pd.read_csv(file_path)
                    self.extracted_data[file_key] = df
                    logger.info(f"✅ Extracted {file_key}: {len(df)} rows, {len(df.columns)} columns")
                except Exception as e:
                    logger.error(f"Failed to extract {file_key}: {str(e)}")
            else:
                logger.warning(f"File not found: {file_path}")
                
        return self.extracted_data
    
    def save_to_bronze(self, data: Dict[str, pd.DataFrame]) -> bool:
        """Save extracted data to bronze layer as Parquet"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for file_key, df in data.items():
            bronze_file = BRONZE_DIR / f"bronze_{file_key}_{timestamp}.parquet"
            df.to_parquet(bronze_file, index=False)
            logger.info(f"Saved bronze layer: {bronze_file.name}")
        
        return True

def extract_bronze_layer() -> bool:
    """Main extraction orchestration"""
    logger.info("=" * 60)
    logger.info("BRONZE LAYER EXTRACTION - Olist Dataset")
    logger.info("=" * 60)
    
    extractor = OlistExtractor()
    data = extractor.extract_all_files()
    
    if not data:
        logger.error("No data extracted")
        return False
    
    # Save to bronze
    extractor.save_to_bronze(data)
    
    # Summary
    logger.info("\n📊 Extraction Summary:")
    for key, df in data.items():
        logger.info(f"  {key}: {len(df):,} records")
    
    return True

if __name__ == "__main__":
    extract_bronze_layer()