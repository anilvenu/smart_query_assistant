import streamlit as st
import pandas as pd
import yaml
import json
import os
import psycopg2
import psycopg2.extras
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime
from dotenv import load_dotenv
import logging

# Set up logging into a file for auditing
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Set up logging to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

# Import custom LLM service
from llm_service import LLMService

# Load environment variables
load_dotenv()

# Configuration
YAML_FILE_PATH = "verified_queries.yaml"

# PostgreSQL connection parameters
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "insurance_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# Set up page configuration
st.set_page_config(page_title="Smart Query Assistant", layout="wide")

# Initialize LLM service
llm_service = LLMService()

# Add CSS styling
st.markdown("""
<style>
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 0;
    }
    .query-box {
        background-color: #1E1E1E;  /* Dark background for SQL */
        color: #FFFFFF;  /* White text */
        padding: 15px;
        border-radius: 5px;
        font-family: monospace;
        margin-bottom: 10px;
        border: 1px solid #333;
    }
    .result-box {
        background-color: #e6ffe6;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .explanation-box {
        background-color: #2D2D2D;  /* Dark background for explanations */
        color: #FFFFFF;  /* White text */
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        border: 1px solid #333;
        line-height: 1.5;
    }
    .source-tag {
        background-color: #ff9999;
        color: white;
        padding: 3px 6px;
        border-radius: 3px;
        font-size: 0.8em;
        margin-right: 10px;
    }
    .match-tag {
        background-color: #99cc99;
        color: white;
        padding: 3px 6px;
        border-radius: 3px;
        font-size: 0.8em;
        margin-right: 10px;
    }
    .llm-info {
        margin-top: 5px;
        font-size: 0.8em;
        color: #888;
    }
    /* SQL syntax highlighting */
    .query-box code {
        color: #569CD6;  /* Light blue for SQL keywords */
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'history' not in st.session_state:
    st.session_state.history = []

# PostgreSQL Connection Helper
def get_pg_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"Error connecting to PostgreSQL: {e}")
        return None

# Function to execute SQL query against PostgreSQL
def execute_sql_query(sql):
    try:
        conn = get_pg_connection()
        if not conn:
            return 500, {"error": "Failed to connect to database"}
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(sql)
        
        # For SELECT queries
        if sql.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            # Convert to DataFrame
            df = pd.DataFrame(results, columns=columns)
            
            cursor.close()
            conn.close()
            return 200, {"rows": df.to_dict('records'), "columnNames": columns}
        # For INSERT, UPDATE, DELETE queries
        else:
            affected_rows = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            return 200, {"affected_rows": affected_rows}
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.close()
        return 500, {"error": str(e)}

# Load verified queries from YAML
def load_verified_queries():
    if os.path.exists(YAML_FILE_PATH):
        with open(YAML_FILE_PATH, 'r') as file:
            try:
                data = yaml.safe_load(file)
                return data.get('verified_queries', []) if data else []
            except yaml.YAMLError:
                st.error(f"Error parsing YAML file: {YAML_FILE_PATH}")
                return []
    return []

# Display query results
def display_query_results(status_code: int, result: Dict[str, Any], sql: str):
    """Helper function to display query results in Streamlit"""
    if status_code == 200:
        if "error" in result:
            st.error(result["error"])
            return
        
        # Display SQL query first
        st.subheader("Executed SQL Query")
        st.code(sql, language="sql")
        
        # Handle the results
        if "rows" in result:
            # Create DataFrame
            df = pd.DataFrame(result["rows"])
            
            # Display results
            st.subheader("Query Results")
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                st.success(f"Found {len(df)} rows")
            else:
                st.info("Query executed successfully but returned no rows.")
        elif "affected_rows" in result:
            st.success(f"Query executed successfully. Affected rows: {result['affected_rows']}")
    else:
        st.error(f"Query execution failed with status code {status_code}")
        st.write("Error Details:", result.get('error', 'Unknown error'))

# Function to get database schema
def get_database_schema():
    try:
        conn = get_pg_connection()
        if not conn:
            return "Failed to connect to database"
        
        cursor = conn.cursor()
        
        # Query to get table information
        cursor.execute("""
            SELECT 
                table_name, 
                column_name, 
                data_type
            FROM 
                information_schema.columns
            WHERE 
                table_schema = 'public'
            ORDER BY 
                table_name, 
                ordinal_position
        """)
        
        schema_info = cursor.fetchall()
        
        # Format the schema information
        schema_text = ""
        current_table = ""
        
        for table, column, data_type in schema_info:
            if table != current_table:
                schema_text += f"\nTABLE: {table}\n"
                current_table = table
            
            schema_text += f"  - {column} ({data_type})\n"
        
        cursor.close()
        conn.close()
        
        return schema_text
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.close()
        return f"Error retrieving schema: {str(e)}"

# Function to check if a question matches any verified query
def find_matching_query(question: str, verified_queries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Use LLM to determine if the question matches a previously answered query."""
    if not verified_queries:
        return None

    # Create a string representation of all verified queries
    queries_str = ""
    for i, query in enumerate(verified_queries):
        queries_str += f"Query {i+1}:\n"
        queries_str += f"Name: {query.get('name', '')}\n"
        queries_str += f"Question: {query.get('question', '')}\n"
        queries_str += f"SQL: {query.get('sql', '')}\n"
        queries_str += f"Explanation: {query.get('query_explanation', '')}\n\n"
    
    # System prompt for query matching
    system_prompt = """You are an expert at matching user questions with verified SQL queries.
Your task is to analyze the user's question and find the most similar verified query."""

    # User prompt with matching rules
    user_prompt = f"""Follow these comparison rules carefully:
1. Core Query Components:
   - What is being counted/summed/averaged?
   - Which time period is being queried?
   - What status or category filters are needed?
   - Are there fields to be dropped from the SELECT clause and GROUP BY clause?
   - Are there fields to be added to the SELECT clause?

2. Pattern Matching:
   - Match main action (count, sum, etc.)
   - Match time period (specific year)
   - Match status (active, inactive, etc.)
   - Look for status values in SQL comments

3. Modification Requirements:
   - List ALL required changes in modifications, if more than one change is needed
   - Include both time period AND categorical value changes when needed
   - Be explicit about which categorical value(s) to use
   - Use values from SQL comments when available
   - Add fields to the SELECT clause if needed and available in comments or already used in WHERE clause

Return a JSON with these fields:
- "match": boolean indicating if a match was found
- "query_number": integer with the matching query number
- "similarity": integer percentage of similarity (0-100)
- "modification_needed": boolean indicating if changes are needed
- "modifications": string describing needed changes if any

Example modifications:
- Multiple changes: "Change year from 2023 to 2022 in WHERE clause AND update policy_status from 'active' to 'lapsed' (value from comment)"
- Status only: "Update status from 'active' to 'inactive' using value from comment"
- Year only: "Change year from 2023 to 2022 in WHERE clause"
- Date change: "Change date from '2023-01-01' to '2022-12-31' in WHERE clause"
- Add field: "Add field 'policy_type' to SELECT clause"
- Remove field: "Remove field 'customer_name' from SELECT clause" and GROUP BY clause because we are counting customers

User Question: {question}

Previously verified queries:
{queries_str}
"""
    
    try:
        with st.spinner("Checking for similar queries..."):
            # Get structured response from LLM
            response_json = llm_service.generate_structured_output(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )
            
            st.write("Debug - LLM response:", response_json)
            
            # Validate response format
            required_keys = {"match", "query_number", "similarity", "modification_needed", "modifications"}
            if not all(key in response_json for key in required_keys):
                st.error(f"Missing required keys in response. Found keys: {list(response_json.keys())}")
                return None
            
            if not response_json["match"]:
                return None
            
            query_number = int(response_json["query_number"])
            if not (0 < query_number <= len(verified_queries)):
                st.error(f"Invalid query number: {query_number}")
                return None
            
            return {
                "verified_query": verified_queries[query_number - 1],
                "similarity": response_json["similarity"],
                "modification_needed": response_json["modification_needed"],
                "modifications": response_json["modifications"]
            }
    except Exception as e:
        st.error(f"Error while checking for query matches: {str(e)}")
        return None

# Function to generate SQL using LLM
def generate_sql_with_llm(question: str, schema_info: str) -> Dict[str, Any]:
    """Generate SQL using the configured LLM."""
    # System prompt for SQL generation
    system_prompt = """You are an expert SQL developer for PostgreSQL. Your task is to generate an optimized SQL query based on a natural language question and the given database schema."""
    
    # User prompt with schema and question
    user_prompt = f"""Database Schema:
{schema_info}

Natural Language Question:
{question}

Think step-by-step and provide:
1. A detailed explanation of your approach to solving this question
2. The optimized PostgreSQL SQL query that answers the question

Return your response as a JSON with these fields:
- "query_explanation": a detailed explanation of your approach
- "sql_query": the complete SQL query
- "answer": a brief answer to the original question based on what the SQL will return
"""
    
    try:
        # Get response from LLM
        with st.spinner("Generating SQL from your question..."):
            response_json = llm_service.generate_structured_output(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )
            
            return response_json
    except Exception as e:
        st.error(f"Error generating SQL: {str(e)}")
        return {}

# Function to adjust SQL based on modifications from the LLM
def adjust_sql(original_sql: str, modifications: str) -> str:
    """Use the LLM to adjust SQL based on the modifications."""
    if not modifications:
        return original_sql
    
    # System prompt for SQL adjustment
    system_prompt = """You are an expert SQL developer for PostgreSQL. Your task is to analyze and modify SQL based on specific requirements."""
    
    # User prompt with original SQL and modifications
    user_prompt = f"""Original SQL:
{original_sql}

Modification instructions:
{modifications}

Rules:
1. Analyze ALL Components:
   - Column aliases: Update to match the context
   - SQL Comments: Extract valid status values
   - WHERE conditions: Year and status filters

2. ONLY modify these parts:
   - Column aliases in SELECT clause to match the question context
   - Date/Year in WHERE clause as requested
   - Status values using options from comments

3. Column Alias Guidelines:
   - Match the verb from user's question
   - Keep prefixes if present
   - Maintain quote style and capitalization

4. Keep Intact:
   - Query structure
   - Table names
   - Aggregation functions
   - Comment content

5. Make sure the response contains ONLY the executable SQL and not any other text
Return only the modified SQL query.
"""
    
    try:
        with st.spinner("Adjusting SQL query..."):
            # Get modified SQL from LLM
            modified_sql = llm_service.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0
            )
            
            return modified_sql.strip()
    except Exception as e:
        st.error(f"Error adjusting SQL: {str(e)}")
        return original_sql

# App header
st.markdown("""
<div class="header-container">
    <h1>Smart Query Assistant</h1>
</div>
""", unsafe_allow_html=True)

# Display LLM provider info
st.markdown(f"<div class='llm-info'>Using LLM provider: {llm_service.provider}</div>", unsafe_allow_html=True)

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # Database connection testing
    if st.button("Test Database Connection"):
        conn = get_pg_connection()
        if conn:
            st.success("Successfully connected to PostgreSQL!")
            conn.close()
    
    # History
    st.header("Query History")
    if st.session_state.history:
        for i, (q, _) in enumerate(reversed(st.session_state.history[-5:])):
            if st.button(f"{q[:40]}{'...' if len(q) > 40 else ''}", key=f"history_{i}"):
                question = q
                st.experimental_rerun()
    else:
        st.info("No query history yet")

# Fetch schema information once
schema_info = get_database_schema()

# Main content
st.header("Ask a Question")

# Input for question
question = st.text_input("Enter your question about insurance data")

if st.button("Submit") and question:
    # Add to history
    if question not in [q for q, _ in st.session_state.history]:
        st.session_state.history.append((question, datetime.now()))
        
    # Section to display results
    st.header("Results")
    
    # Load verified queries
    verified_queries = load_verified_queries()
    
    # Check if the question matches any verified query
    match_info = None
    if verified_queries:
        match_info = find_matching_query(question, verified_queries)
    
    if match_info:
        verified_query = match_info["verified_query"]
        st.markdown(f"<span class='match-tag'>MATCHED QUERY</span> Found a similar verified query: '{verified_query.get('name')}'", unsafe_allow_html=True)
        
        # Display similarity information
        st.markdown(f"**Similarity:** {match_info.get('similarity')}%")
        
        # Get the SQL from the verified query
        sql = verified_query.get("sql", "")
        
        # Check if modifications are needed
        if match_info.get("modification_needed", False):
            st.info(f"Modifications needed: {match_info.get('modifications', '')}")
            
            # Adjust the SQL based on the modifications
            adjusted_sql = adjust_sql(sql, match_info.get("modifications", ""))
            
            st.subheader("Original SQL")
            st.markdown(f"<div class='query-box'>{sql}</div>", unsafe_allow_html=True)
            
            st.subheader("Adjusted SQL")
            st.markdown(f"<div class='query-box'>{adjusted_sql}</div>", unsafe_allow_html=True)
            
            # Use the adjusted SQL
            sql = adjusted_sql
        else:
            # Display the original SQL
            st.subheader("SQL Query")
            st.markdown(f"<div class='query-box'>{sql}</div>", unsafe_allow_html=True)
        
        # Execute the query and display results
        status_code, result = execute_sql_query(sql)
        display_query_results(status_code, result, sql)
        
        # Display explanation
        if verified_query.get("query_explanation"):
            st.subheader("Query Explanation")
            st.markdown(f'<div class="explanation-box">{verified_query["query_explanation"]}</div>', unsafe_allow_html=True)
        
        # Log the verified query used, the modifications, and the SQL executed
        logging.info(f"Used verified query: {verified_query['name']}")
        logging.info(f"Modifications: {match_info.get('modifications', '')}")
        logging.info(f"Executed SQL: {sql}")
    else:
        # If no match is found, use LLM to generate a query
        st.markdown("<span class='source-tag'>AI GENERATED</span> No matching verified query found. Using AI to generate an answer.", unsafe_allow_html=True)
        
        # Generate SQL using LLM
        ai_result = generate_sql_with_llm(question, schema_info)
        
        if ai_result:
            # Display the AI's answer   
            if "answer" in ai_result:
                st.subheader("Answer")
                st.markdown(f"<div class='result-box'>{ai_result.get('answer', '')}</div>", unsafe_allow_html=True)
                
            # Display the SQL query
            st.subheader("Generated SQL")
            sql_query = ai_result.get('sql_query', '')
            st.markdown(f"<div class='query-box'>{sql_query}</div>", unsafe_allow_html=True)
            
            # Execute the query
            if sql_query:
                status_code, result = execute_sql_query(sql_query)
                display_query_results(status_code, result, sql_query)
            
            # Display the explanation
            if "query_explanation" in ai_result:
                st.subheader("Explanation")
                st.markdown(f"<div class='explanation-box'>{ai_result.get('query_explanation', '')}</div>", unsafe_allow_html=True)
        else:
            st.error("Failed to generate SQL for your question. Please try a different question.")

# Footer
st.markdown("---")
st.markdown("Smart Query Assistant | Built for Insurance Analytics")