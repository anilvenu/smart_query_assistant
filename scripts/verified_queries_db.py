"""
Database initialization script for Smart Query Assistant.

This script creates the necessary database tables and loads verified queries from YAML.
"""
import os
import yaml
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime
from sentence_transformers import SentenceTransformer

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.helper import Question

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection parameters
DB_NAME = "application_db"
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Load the sentence transformer model for embeddings
model = SentenceTransformer('all-MiniLM-L6-v2')

def create_database():
    """Create the database if it doesn't exist."""
    # Connect to PostgreSQL server
    conn = psycopg2.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
    exists = cursor.fetchone()
    
    if not exists:
        logger.info(f"Creating database {DB_NAME}...")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        logger.info(f"Database {DB_NAME} created successfully.")
    else:
        logger.info(f"Database {DB_NAME} already exists.")
    
    cursor.close()
    conn.close()

def drop_tables():
    """Drop tables in the database."""
    # Connect to the database
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Drop verified_query table
    cursor.execute("""DROP TABLE IF  EXISTS verified_query CASCADE""")
    
    # Drop follow_up table
    cursor.execute("""DROP TABLE IF  EXISTS follow_up CASCADE""")

    # Drop index on vector embedding
    cursor.execute("""DROP INDEX IF EXISTS idx_question_vector_embedding""")

    # Drop question table
    cursor.execute("""DROP TABLE IF  EXISTS question CASCADE""")
    
    
    logger.info("Tables dropped successfully.")
    cursor.close()
    conn.close()


def create_tables():
    """Create tables in the database."""
    # Connect to the database
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Enable vector extension
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Create verified_query table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verified_query (
        id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        query_explanation TEXT NOT NULL,
        sql TEXT NOT NULL,
        instructions TEXT,
        tables_used TEXT[],
        verified_at TIMESTAMP NOT NULL,
        verified_by VARCHAR(50) NOT NULL
    )
    """)
    
    # Create follow_up table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS follow_up (
        id SERIAL PRIMARY KEY,
        source_query_id VARCHAR(50) NOT NULL REFERENCES verified_query(id) ON DELETE CASCADE,
        target_query_id VARCHAR(50) NOT NULL REFERENCES verified_query(id) ON DELETE CASCADE,
        UNIQUE (source_query_id, target_query_id)
    )
    """)
    
    # Create question table with vector support
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS question (
        id SERIAL PRIMARY KEY,
        question_text TEXT NOT NULL,
        verified_query_id VARCHAR(50) NOT NULL REFERENCES verified_query(id) ON DELETE CASCADE,
        vector_embedding vector(384),
        UNIQUE (question_text, verified_query_id)
    )
    """)
    
    # Create index on vector embedding
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_question_vector_embedding 
    ON question USING ivfflat (vector_embedding vector_cosine_ops)
    """)
    
    logger.info("Tables created successfully.")
    cursor.close()
    conn.close()

def load_yaml_data(yaml_file_path):
    """Load verified queries from YAML file."""
    try:
        with open(yaml_file_path, 'r') as file:
            data = yaml.safe_load(file)
            queries = data.get('verified_queries', [])
            logger.info(f"Loaded {len(queries)} queries from YAML file")
            return queries
    except Exception as e:
        logger.error(f"Error loading YAML data: {str(e)}")
        return []

def insert_verified_queries(verified_queries):
    """Insert verified queries into the database."""
    # Connect to the database
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    conn.autocommit = False
    cursor = conn.cursor()
    
    try:
        # Insert verified queries first
        for vq in verified_queries:
            # Parse verified_at timestamp if it's a string
            verified_at = vq.get('verified_at')
            if isinstance(verified_at, str):
                try:
                    verified_at = datetime.strptime(verified_at, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # Try alternative format
                    try:
                        verified_at = datetime.strptime(verified_at, "%d %B %Y")
                    except ValueError:
                        # Default to current time if parsing fails
                        verified_at = datetime.now()
            
            # Process the SQL query (strip any trailing whitespace)
            sql = vq.get('sql', '').strip()
            
            # Insert the verified query
            cursor.execute("""
            INSERT INTO verified_query (id, name, query_explanation, sql, instructions, tables_used, verified_at, verified_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name,
                query_explanation = EXCLUDED.query_explanation,
                sql = EXCLUDED.sql,
                instructions = EXCLUDED.instructions,
                tables_used = EXCLUDED.tables_used,
                verified_at = EXCLUDED.verified_at,
                verified_by = EXCLUDED.verified_by
            """, (
                vq.get('id'),
                vq.get('name'),
                vq.get('query_explanation'),
                sql,
                vq.get('instructions'),
                vq.get('tables_used', []),
                verified_at,
                vq.get('verified_by', 'data_analyst')
            ))
        
        conn.commit()
        logger.info(f"Inserted {len(verified_queries)} verified queries.")
        
        # Now insert questions with vector embeddings
        processed_questions = 0
        
        for vq in verified_queries:
            query_id = vq.get('id')
            questions = vq.get('questions', [])
            
            # Handle both list and single question formats
            if isinstance(questions, str):
                questions = [questions]
            
            # Delete existing questions for this query
            cursor.execute("DELETE FROM question WHERE verified_query_id = %s", (query_id,))
            
            for question_text in questions:
                # Generate embedding
                embedding = model.encode(question_text)
                embedding_vector = embedding.tolist()
                
                cursor.execute("""
                INSERT INTO question (question_text, verified_query_id, vector_embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (question_text, verified_query_id) DO UPDATE
                SET vector_embedding = EXCLUDED.vector_embedding
                """, (
                    question_text,
                    query_id,
                    embedding_vector
                ))
                processed_questions += 1
        
        conn.commit()
        logger.info(f"Processed {processed_questions} questions with vector embeddings.")
        
        # Finally insert follow-up relations
        # First delete existing follow-ups
        cursor.execute("DELETE FROM follow_up")
        conn.commit()
        
        inserted_follow_ups = 0
        for vq in verified_queries:
            source_id = vq.get('id')
            follow_ups = vq.get('follow_up', [])
            
            for target_id in follow_ups:
                # Check if target query exists before inserting
                cursor.execute("SELECT 1 FROM verified_query WHERE id = %s", (target_id,))
                if cursor.fetchone():  # Only insert if target exists
                    cursor.execute("""
                    INSERT INTO follow_up (source_query_id, target_query_id)
                    VALUES (%s, %s)
                    ON CONFLICT (source_query_id, target_query_id) DO NOTHING
                    """, (source_id, target_id))
                    inserted_follow_ups += 1
                else:
                    logger.warning(f"Skipping follow-up relation: {source_id} -> {target_id} (target does not exist)")
        
        conn.commit()
        logger.info(f"Inserted {inserted_follow_ups} follow-up relations.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting data: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function to initialize the database and load data."""
    yaml_file_path = "app/verified_queries.yaml"
    
    # Create database and tables
    create_database()
    drop_tables()
    create_tables()
    
    # Load and insert data from YAML
    verified_queries = load_yaml_data(yaml_file_path)
    if verified_queries:
        insert_verified_queries(verified_queries)
    
    logger.info("Database initialization completed successfully.")

if __name__ == "__main__":
    main()