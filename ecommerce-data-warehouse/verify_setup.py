"""
Project Setup Verification Script
Run this to verify everything is configured correctly
"""

import sys
import os
from pathlib import Path
import importlib
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_python_version():
    """Verify Python version"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        logger.info(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        logger.error(f"❌ Python 3.8+ required. Found: {version.major}.{version.minor}")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    required = [
        'pandas',
        'sqlalchemy', 
        'pymysql',
        'dotenv',
        'pyarrow'
    ]
    
    missing = []
    for package in required:
        try:
            importlib.import_module(package)
            logger.info(f"✅ {package} installed")
        except ImportError:
            missing.append(package)
            logger.error(f"❌ {package} not installed")
    
    if missing:
        logger.error(f"\nInstall missing packages: pip install {' '.join(missing)}")
        return False
    return True

def check_folder_structure():
    """Verify all required folders exist"""
    folders = [
        'data/raw',
        'data/bronze', 
        'data/silver',
        'data/gold',
        'logs',
        'notebooks',
        'sql',
        'config',
        'scripts',
        'dashboards'
    ]
    
    all_exist = True
    for folder in folders:
        path = Path(folder)
        if path.exists():
            logger.info(f"✅ {folder}/ exists")
        else:
            logger.warning(f"⚠️  {folder}/ missing - creating...")
            path.mkdir(parents=True, exist_ok=True)
            all_exist = False
    
    return True

def check_olist_files():
    """Check if Olist dataset files are present"""
    expected_files = [
        'olist_customers_dataset.csv',
        'olist_orders_dataset.csv',
        'olist_products_dataset.csv',
        'olist_order_items_dataset.csv',
        'olist_sellers_dataset.csv'
    ]
    
    raw_dir = Path('data/raw')
    if not raw_dir.exists():
        logger.error("❌ data/raw/ directory not found")
        return False
    
    found_files = []
    missing_files = []
    
    for file in expected_files:
        file_path = raw_dir / file
        if file_path.exists():
            size_mb = file_path.stat().st_size / 1024 / 1024
            found_files.append(f"{file} ({size_mb:.1f}MB)")
            logger.info(f"✅ {file} found")
        else:
            missing_files.append(file)
            logger.warning(f"⚠️  {file} missing")
    
    if missing_files:
        logger.error(f"\nMissing {len(missing_files)} files. Please download Olist dataset from:")
        logger.error("https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        logger.error("\nPlace CSV files in data/raw/ directory")
        return False
    
    logger.info(f"\n✅ Found all {len(found_files)} Olist data files")
    return True

def check_database_connection():
    """Test MySQL connection"""
    try:
        from config.config import get_db_connection_string
        from sqlalchemy import create_engine, text
        
        conn_string = get_db_connection_string()
        engine = create_engine(conn_string)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0][:30]
            logger.info(f"✅ MySQL connected: {version}...")
            
            # Check if database exists
            result = conn.execute(text("SELECT DATABASE()"))
            db_name = result.fetchone()[0]
            logger.info(f"✅ Database: {db_name}")
            
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        logger.info("\nPlease ensure MySQL is running and .env is configured:")
        logger.info("1. Start the MySQL service")
        logger.info("2. Check .env file has correct credentials")
        return False

def check_schema():
    """Verify database schema is created"""
    try:
        from config.config import get_db_connection_string
        from sqlalchemy import create_engine, text
        
        engine = create_engine(get_db_connection_string())
        
        with engine.connect() as conn:
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                AND table_name IN ('fact_orders', 'dim_customer', 'dim_product')
            """))
            
            tables = [row[0] for row in result]
            
            if 'fact_orders' in tables:
                logger.info("✅ Schema tables found")
                
                # Get row counts
                for table in ['fact_orders', 'dim_customer', 'dim_product']:
                    if table in tables:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
                        logger.info(f"   {table}: {count:,} rows")
                return True
            else:
                logger.warning("⚠️  Schema not initialized")
                logger.info("Run: mysql -u <user> -p ecommerce_dw < sql/schema_mysql.sql")
                return False
                
    except Exception as e:
        logger.error(f"❌ Schema check failed: {str(e)}")
        return False

def check_environment_file():
    """Check if .env file exists and has required variables"""
    env_path = Path('.env')
    if env_path.exists():
        logger.info("✅ .env file found")
        
        # Check required variables
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing in .env: {', '.join(missing_vars)}")
            return False
        
        logger.info("✅ Environment variables configured")
        return True
    else:
        logger.warning("⚠️  .env file not found")
        logger.info("Copy .env.example to .env and configure your database credentials")
        return False

def run_quick_test():
    """Run a quick ETL test with small sample"""
    logger.info("\n" + "="*50)
    logger.info("RUNNING QUICK ETL TEST")
    logger.info("="*50)
    
    try:
        # Try to load a small sample of orders
        import pandas as pd
        from scripts.extract import extract_bronze_layer
        from scripts.transform import transform_silver_layer
        
        logger.info("Testing extract...")
        extract_bronze_layer()
        
        logger.info("Testing transform...")
        transform_silver_layer()
        
        logger.info("✅ Quick test passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Quick test failed: {str(e)}")
        return False

def main():
    """Run all verification checks"""
    print("\n" + "="*60)
    print("📊 OLIST DATA WAREHOUSE - SETUP VERIFICATION")
    print("="*60 + "\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Folder Structure", check_folder_structure),
        ("Environment File", check_environment_file),
        ("Olist Data Files", check_olist_files),
        ("Database Connection", check_database_connection),
        ("Schema Creation", check_schema),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n--- {check_name} ---")
        result = check_func()
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"\n✅ ALL CHECKS PASSED! ({passed}/{total})")
        print("\n🎉 Your project is ready to run!")
        print("\nNext steps:")
        print("1. Run: python main.py --stage all")
        print("2. Run: mysql -u <user> -p ecommerce_dw < sql/analytics_queries.sql")
        print("3. Open: jupyter notebook notebooks/exploration.ipynb")
        
        # Ask if user wants to run quick test
        response = input("\nRun quick ETL test? (y/n): ")
        if response.lower() == 'y':
            run_quick_test()
            
    else:
        print(f"\n⚠️  {total - passed} checks failed. Please fix issues above.")
        print("\nTroubleshooting tips:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Olist CSV files already belong in data/raw/")
        print("3. Configure .env file with MySQL credentials")
        print("4. Create the MySQL database and load sql/schema_mysql.sql")

if __name__ == "__main__":
    main()