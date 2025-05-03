"""
Script to recreate verified_queries.yaml file with proper formatting.
Fixed version that handles string representation correctly.
"""
import os
import psycopg2
import psycopg2.extras
import yaml
import logging
import re
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection parameters
DB_CONFIG = {
    "dbname": "application_db",
    "user": "postgres",
    "password": "",  # Replace with your password if needed
    "host": "localhost",
    "port": "5432"
}

def get_verified_queries(conn):
    """Retrieve all verified queries from the database."""
    query = """
    SELECT * FROM verified_query
    ORDER BY id
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
        cursor.execute(query)
        verified_queries = [dict(row) for row in cursor.fetchall()]
    
    return verified_queries

def get_questions_for_query(conn, query_id):
    """Retrieve all questions for a specific verified query."""
    query = """
    SELECT question_text
    FROM question
    WHERE verified_query_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (query_id,))
        questions = [row[0] for row in cursor.fetchall()]
    
    return questions

def get_follow_ups_for_query(conn, query_id):
    """Retrieve all follow-up query IDs for a specific verified query."""
    query = """
    SELECT target_query_id
    FROM follow_up
    WHERE source_query_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (query_id,))
        follow_ups = [row[0] for row in cursor.fetchall()]
    
    return follow_ups

def write_custom_yaml(data, filename):
    """
    Write data to a YAML file with custom formatting.
    Uses string manipulation instead of PyYAML representers to avoid serialization issues.
    """
    with open(filename, 'w') as file:
        file.write("verified_queries:\n")
        
        for query in data["verified_queries"]:
            file.write(f"- id: {query['id']}\n")
            file.write(f"  name: {query['name']}\n")
            
            # Process query explanation (folded style '>')
            explanation = query['query_explanation']
            file.write("  query_explanation: >\n")
            for line in explanation.strip().split('\n'):
                file.write(f"    {line}\n")
            
            # Process questions (dash list style with indentation)
            file.write("  questions: \n")
            for question in query['questions']:
                file.write(f"    - {question}\n")
            
            # Process instructions (folded style '>')
            instructions = query['instructions'] if query['instructions'] else ""
            file.write("  instructions: >\n")
            for line in instructions.strip().split('\n'):
                file.write(f"    {line}\n")
            
            # Process SQL (literal style '|')
            sql = query['sql']
            file.write("  sql: |\n")
            for line in sql.strip().split('\n'):
                file.write(f"    {line}\n")
            
            # Process tables_used
            file.write("  tables_used:\n")
            for table in query['tables_used']:
                file.write(f"  - {table}\n")
            
            # Process follow_up
            file.write("  follow_up:\n")
            for follow_up in query['follow_up']:
                file.write(f"    - {follow_up}\n")
            
            # Process verified_at and verified_by
            file.write(f"  verified_at: {query['verified_at']}\n")
            file.write(f"  verified_by: {query['verified_by']}\n")
            
            # Add a blank line between queries
            file.write("\n")
    
    return filename

def main():
    """Main function to recreate verified_queries.yaml."""
    try:
        # Connect to the database
        logger.info("Connecting to application_db...")
        conn = psycopg2.connect(**DB_CONFIG)
        
        # Get all verified queries
        verified_queries = get_verified_queries(conn)
        logger.info(f"Found {len(verified_queries)} verified queries")
        
        # Prepare data structure
        yaml_data = {"verified_queries": []}
        
        for vq in verified_queries:
            query_id = vq['id']
            
            # Get questions and follow-ups
            questions = get_questions_for_query(conn, query_id)
            follow_ups = get_follow_ups_for_query(conn, query_id)
            
            # Format timestamp
            verified_at = vq['verified_at']
            if isinstance(verified_at, datetime):
                verified_at = verified_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Create entry
            query_entry = {
                "id": query_id,
                "name": vq['name'],
                "query_explanation": vq['query_explanation'],
                "questions": questions,
                "instructions": vq['instructions'],
                "sql": vq['sql'],
                "tables_used": vq['tables_used'] if vq['tables_used'] else [],
                "follow_up": follow_ups,
                "verified_at": verified_at,
                "verified_by": vq['verified_by']
            }
            
            yaml_data["verified_queries"].append(query_entry)
            logger.info(f"Processed query {query_id} with {len(questions)} questions and {len(follow_ups)} follow-ups")
        
        # Generate YAML file with custom formatting
        output_file = "verified_queries.yaml"
        write_custom_yaml(yaml_data, output_file)
        logger.info(f"YAML file created successfully: {output_file}")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    main()