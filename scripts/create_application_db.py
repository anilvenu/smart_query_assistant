import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from app
from app.config import APPLICATION_DB_CONFIG
from app.db.schema import APPLICATION_DB_TABLES, APPLICATION_DB_INDEXES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_database():
    """Create the application database if it doesn't exist."""
    # Connect to default postgres database first
    db_config = APPLICATION_DB_CONFIG.copy()
    db_name = db_config.pop('dbname')
    
    try:
        conn = psycopg2.connect(**db_config, dbname='postgres')
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        with conn.cursor() as cursor:
            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cursor.fetchone()
            
            if not exists:
                logger.info(f"Creating database: {db_name}")
                cursor.execute(f'CREATE DATABASE {db_name}')
                logger.info(f"Database {db_name} created successfully")
            else:
                logger.info(f"Database {db_name} already exists")
                
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        return False

def create_tables():
    """Create application database tables."""
    try:
        conn = psycopg2.connect(**APPLICATION_DB_CONFIG)
        
        with conn.cursor() as cursor:
            for table_name, table_sql in APPLICATION_DB_TABLES.items():
                logger.info(f"Creating table: {table_name}")
                cursor.execute(table_sql)
            
            conn.commit()
            
            # Create indexes
            for index_sql in APPLICATION_DB_INDEXES:
                logger.info(f"Creating index: {index_sql}")
                cursor.execute(index_sql)
            
            conn.commit()
            
        conn.close()
        logger.info("All tables and indexes created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

def main():
    """Main execution function."""
    logger.info("Starting application database setup")
    
    # Create database
    if create_database():
        # Create tables
        if create_tables():
            logger.info("Application database setup completed successfully")
        else:
            logger.error("Failed to create tables")
    else:
        logger.error("Failed to create database")

if __name__ == "__main__":
    main()