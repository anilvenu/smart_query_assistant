import os
import sys
import logging
import pandas as pd

# Add the project root to the Python path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from app
from app.config import BUSINESS_DB_CONFIG, APPLICATION_DB_CONFIG
from app.db.db_helper import DBHelper
from app.db.conversation_store import ConversationStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_business_database():
    """Check the business database connection and tables."""
    logger.info("Checking business database...")
    
    business_db = DBHelper(BUSINESS_DB_CONFIG, application_db=False)
    
    try:
        # Test connection
        conn = business_db.connect()
        if conn and not conn.closed:
            logger.info("Business database connection successful")
            
            # Check tables
            tables = business_db.get_tables()
            logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
            
            # Check sample data
            if "agencies" in tables:
                success, result = business_db.execute_query("SELECT COUNT(*) FROM agencies")
                if success and isinstance(result, pd.DataFrame) and not result.empty:
                    count = result.iloc[0, 0]
                    logger.info(f"Found {count} agencies in the database")
                    
                    if count == 0:
                        logger.warning("No data found in agencies table. Database may be empty.")
            
            business_db.close()
            return True
        else:
            logger.error("Failed to connect to business database")
            return False
            
    except Exception as e:
        logger.error(f"Error checking business database: {str(e)}")
        return False

def check_application_database():
    """Check the application database connection and tables."""
    logger.info("Checking application database...")
    
    app_db = DBHelper(APPLICATION_DB_CONFIG, application_db=True)
    
    try:
        # Test connection
        conn = app_db.connect()
        if conn and not conn.closed:
            logger.info("Application database connection successful")
            
            # Check tables
            tables = app_db.get_tables()
            
            expected_tables = [
                "conversations", "messages", "query_executions", 
                "visualizations", "vector_embeddings"
            ]
            
            missing_tables = [t for t in expected_tables if t not in tables]
            
            if missing_tables:
                logger.warning(f"Missing tables: {', '.join(missing_tables)}")
                logger.info("Application database tables need to be created")
                return False
            else:
                logger.info(f"Found all required tables: {', '.join(tables)}")
                
                # Test basic functionality
                logger.info("Testing conversation store...")
                
                conversation_store = ConversationStore(app_db)
                
                # Create test conversation
                conversation_id = conversation_store.create_conversation("Test Conversation")
                
                if conversation_id:
                    logger.info(f"Created test conversation: {conversation_id}")
                    
                    # Add test message
                    message_id = conversation_store.add_message(
                        conversation_id, 
                        "user", 
                        "This is a test message",
                        {"test_key": "test_value"}
                    )
                    
                    if message_id:
                        logger.info(f"Added test message: {message_id}")
                        
                        # Clean up test data
                        conversation_store.delete_conversation(conversation_id)
                        logger.info("Deleted test conversation")
                    else:
                        logger.error("Failed to add test message")
                
                app_db.close()
                return True
        else:
            logger.error("Failed to connect to application database")
            return False
            
    except Exception as e:
        logger.error(f"Error checking application database: {str(e)}")
        return False

def main():
    """Main execution function."""
    logger.info("Starting database initialization check")
    
    # Check business database
    business_ok = check_business_database()
    
    # Check application database
    application_ok = check_application_database()
    
    if business_ok and application_ok:
        logger.info("Both databases are properly configured and accessible")
    else:
        if not business_ok:
            logger.error("Business database check failed")
        
        if not application_ok:
            logger.error("Application database check failed")
            logger.info("Run create_application_db.py to set up the application database")

if __name__ == "__main__":
    main()