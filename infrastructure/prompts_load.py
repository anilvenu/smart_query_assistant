import json
import os
from sqlalchemy import create_engine, text
from datetime import datetime
import logging



# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Database connection parameters
DB_NAME = "application_db"
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Path to prompts data file
PROMPTS_DATA_PATH = "data/prompts.json"

def migrate_prompts():
    """Load prompts from JSON file into database tables."""
    try:
        # Check if the data file exists
        if not os.path.exists(PROMPTS_DATA_PATH):
            logger.error(f"Prompts data file not found: {PROMPTS_DATA_PATH}")
            return False
        
        # Load prompts data from JSON file
        with open(PROMPTS_DATA_PATH, 'r') as f:
            prompts_data = json.load(f)
        
        logger.info(f"Loaded {len(prompts_data)} prompts from {PROMPTS_DATA_PATH}")
        
        # Connect to database
        engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

        with engine.connect() as conn:
            # Insert each prompt and its parameters
            for prompt in prompts_data:
                # Check if prompt already exists
                result = conn.execute(
                    text("SELECT id FROM prompts WHERE id = :id"),
                    {"id": prompt['id']}
                )
                
                if result.fetchone():
                    logger.info(f"Prompt '{prompt['id']}' already exists, updating...")
                    # Update existing prompt
                    conn.execute(
                        text("""
                        UPDATE prompts
                        SET name = :name,
                            description = :description,
                            system_prompt = :system_prompt,
                            user_prompt = :user_prompt,
                            verbose_flag = :verbose_flag,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :id
                        """),
                        {
                            "id": prompt['id'],
                            "name": prompt['name'],
                            "description": prompt['description'],
                            "system_prompt": prompt['system_prompt'],
                            "user_prompt": prompt['user_prompt'],
                            "verbose_flag": prompt.get('verbose_flag', False)
                        }
                    )
                else:
                    logger.info(f"Creating new prompt '{prompt['id']}'...")
                    # Insert new prompt
                    conn.execute(
                        text("""
                        INSERT INTO prompts (id, name, description, system_prompt, user_prompt, verbose_flag)
                        VALUES (:id, :name, :description, :system_prompt, :user_prompt, :verbose_flag)
                        """),
                        {
                            "id": prompt['id'],
                            "name": prompt['name'],
                            "description": prompt['description'],
                            "system_prompt": prompt['system_prompt'],
                            "user_prompt": prompt['user_prompt'],
                            "verbose_flag": prompt.get('verbose_flag', False)
                        }
                    )
                
                # Delete existing parameters for this prompt
                conn.execute(
                    text("DELETE FROM prompt_parameters WHERE prompt_id = :prompt_id"),
                    {"prompt_id": prompt['id']}
                )
                
                # Insert parameters
                for param in prompt.get('parameters', []):
                    conn.execute(
                        text("""
                        INSERT INTO prompt_parameters 
                        (prompt_id, param_name, description, default_value, required)
                        VALUES (:prompt_id, :param_name, :description, :default_value, :required)
                        """),
                        {
                            "prompt_id": prompt['id'],
                            "param_name": param['param_name'],
                            "description": param['description'],
                            "default_value": param.get('default_value'),
                            "required": param.get('required', True)
                        }
                    )
            
            # Commit the transaction
            conn.commit()
            
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    migrate_prompts()