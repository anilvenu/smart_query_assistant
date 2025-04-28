import streamlit as st
from streamlit.delta_generator import DeltaGenerator
import pandas as pd
import yaml
import json
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Import custom components
from config import (
    BUSINESS_DB_CONFIG, APPLICATION_DB_CONFIG, 
    YAML_FILE_PATH, DEBUG_MODE
)
from db.db_helper import DBHelper
from db.conversation_store import ConversationStore
from llm_service import LLMService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)
logger = logging.getLogger(__name__)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Set up page configuration
st.set_page_config(page_title="Smart Query Assistant", layout="wide")

# Initialize database helpers
business_db = DBHelper(BUSINESS_DB_CONFIG, application_db=False)
application_db = DBHelper(APPLICATION_DB_CONFIG, application_db=True)

# Initialize components
llm_service = LLMService()
conversation_store = ConversationStore(application_db)

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
if 'conversation_id' not in st.session_state:
    # Create a new conversation
    conversation_id = conversation_store.create_conversation("New Conversation")
    if conversation_id:
        st.session_state.conversation_id = conversation_id
    else:
        st.error("Failed to create conversation. Please check database connection.")
        st.stop()

# Function to execute SQL query against PostgreSQL
def execute_sql_query(sql):
    """Execute SQL query and record execution metrics."""
    start_time = datetime.now()
    
    try:
        # Execute query using business_db
        success, result = business_db.execute_query(sql)
        
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        if success and isinstance(result, pd.DataFrame):
            # Format for compatibility with old code
            return 200, {
                "rows": result.to_dict('records'),
                "columnNames": result.columns.tolist()
            }
        else:
            # Error case
            return 500, {"error": str(result)}
            
    except Exception as e:
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.error(f"Query execution error: {str(e)}")
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
def display_query_results(status_code: int, result: Dict[str, Any], sql: str, message_id: Optional[str] = None):
    """Helper function to display query results in Streamlit"""
    if status_code == 200:
        if "error" in result:
            st.error(result["error"])
            
            # Record query execution failure
            if message_id:
                conversation_store.add_query_execution(
                    message_id=message_id,
                    sql_query=sql,
                    status="error",
                    error_message=result["error"]
                )
            return
        
        # Display SQL query first
        with st.expander("SQL Query", expanded=False):
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
                
                # Record query execution success
                if message_id:
                    conversation_store.add_query_execution(
                        message_id=message_id,
                        sql_query=sql,
                        status="success",
                        row_count=len(df),
                        execution_time_ms=None  # We don't have this information here
                    )
                
                # TODO: In next phase, add visualization generation here
                
            else:
                st.info("Query executed successfully but returned no rows.")
                
                # Record query execution success with zero rows
                if message_id:
                    conversation_store.add_query_execution(
                        message_id=message_id,
                        sql_query=sql,
                        status="success",
                        row_count=0
                    )
                    
        elif "affected_rows" in result:
            st.success(f"Query executed successfully. Affected rows: {result['affected_rows']}")
            
            # Record non-SELECT query execution
            if message_id:
                conversation_store.add_query_execution(
                    message_id=message_id,
                    sql_query=sql,
                    status="success",
                    row_count=result['affected_rows']
                )
    else:
        st.error(f"Query execution failed with status code {status_code}")
        st.write("Error Details:", result.get('error', 'Unknown error'))
        
        # Record query execution failure
        if message_id:
            conversation_store.add_query_execution(
                message_id=message_id,
                sql_query=sql,
                status="error",
                error_message=result.get('error', 'Unknown error')
            )

# Function to get database schema
def get_database_schema():
    return business_db.get_schema_info()

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
            
            if DEBUG_MODE:
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
        logger.error(f"Error while checking for query matches: {str(e)}")
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
        logger.error(f"Error generating SQL: {str(e)}")
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
        logger.error(f"Error adjusting SQL: {str(e)}")
        return original_sql

# Function to render conversation messages
def render_conversation_messages():
    """Render all messages in the current conversation."""
    messages = conversation_store.get_messages(st.session_state.conversation_id)
    
    for message in messages:
        if message['role'] == 'user':
            st.text_input(
                "You:",
                value=message['content'],
                key=f"user_msg_{message['message_id']}",
                disabled=True
            )
        else:
            st.markdown(f"**Assistant:**")
            st.markdown(message['content'])
            
            # Show SQL and results if available in metadata
            if message.get('metadata') and 'sql' in message.get('metadata', {}):
                sql = message['metadata']['sql']
                with st.expander("SQL Query", expanded=False):
                    st.code(sql, language="sql")


# App header
st.markdown("""
<div class="header-container">
    <h1>Smart Query Assistant</h1>
</div>
""", unsafe_allow_html=True)

# Display LLM provider info
st.markdown(f"<div class='llm-info'>Using LLM provider: {llm_service.provider}</div>", unsafe_allow_html=True)

# Sidebar for configuration and conversation management
with st.sidebar:
    st.header("Conversations")
    
    # Show current conversation title
    current_conversation = conversation_store.get_conversation(st.session_state.conversation_id)
    if current_conversation:
        current_title = current_conversation['title']
    else:
        current_title = "New Conversation"
    
    st.text_input("Current Conversation", value=current_title, disabled=True)
    
    # New conversation button
    if st.button("New Conversation"):
        new_id = conversation_store.create_conversation("New Conversation")
        if new_id:
            st.session_state.conversation_id = new_id
            st.rerun()
    
    # Show past conversations
    st.subheader("Past Conversations")
    conversations = conversation_store.get_conversations()
    
    for conv in conversations:
        if st.button(f"{conv['title']} ({conv['message_count']} messages)" if 'message_count' in conv else conv['title'], key=f"conv_{conv['conversation_id']}"):
            st.session_state.conversation_id = conv['conversation_id']
            st.rerun()

# Fetch schema information once
schema_info = get_database_schema()

# Main content - show current conversation
st.header("Conversation")

# Render previous messages in the conversation
render_conversation_messages()

# Input for new question
st.header("Ask a Question")
question = st.text_input("Enter your question about insurance data")

if st.button("Submit") and question:
    # Add user message to conversation
    user_message_id = conversation_store.add_message(
        st.session_state.conversation_id, 
        "user", 
        question
    )
    
    if not user_message_id:
        st.error("Failed to save your message. Please check database connection.")
        st.stop()
    
    # Section to display results
    st.header("Processing Your Question")
    
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
        
        # Create the assistant message
        assistant_message = f"I found a relevant query for '{verified_query.get('name', 'your question')}'."
        
        # Check if modifications are needed
        modifications_text = ""
        if match_info.get("modification_needed", False):
            modifications_text = f"I needed to make some adjustments: {match_info.get('modifications', '')}"
            st.info(f"Modifications needed: {match_info.get('modifications', '')}")
            
            # Adjust the SQL based on the modifications
            adjusted_sql = adjust_sql(sql, match_info.get("modifications", ""))
            
            with st.expander("Original vs Adjusted SQL", expanded=False):
                st.subheader("Original SQL")
                st.code(sql, language="sql")
                
                st.subheader("Adjusted SQL")
                st.code(adjusted_sql, language="sql")
            
            # Use the adjusted SQL
            sql = adjusted_sql
            
            # Update assistant message
            assistant_message += f"\n\n{modifications_text}"
        else:
            # Display the original SQL
            with st.expander("SQL Query", expanded=False):
                st.code(sql, language="sql")
        
        # Add explanation to assistant message
        if verified_query.get("query_explanation"):
            assistant_message += f"\n\n{verified_query['query_explanation']}"
            with st.expander("Query Explanation", expanded=False):
                st.markdown(verified_query["query_explanation"])
        
        # Add assistant message to conversation
        assistant_message_id = conversation_store.add_message(
            st.session_state.conversation_id,
            "assistant",
            assistant_message,
            {"sql": sql, "verified_query_name": verified_query.get("name")}
        )
        
        # Execute the query and display results
        status_code, result = execute_sql_query(sql)
        display_query_results(status_code, result, sql, assistant_message_id)
        
    else:
        # If no match is found, use LLM to generate a query
        st.markdown("<span class='source-tag'>AI GENERATED</span> No matching verified query found. Using AI to generate an answer.", unsafe_allow_html=True)
        
        # Generate SQL using LLM
        ai_result = generate_sql_with_llm(question, schema_info)
        
        if ai_result:
            # Prepare assistant message
            assistant_message = "I've generated a new SQL query to answer your question."
            
            # Add explanation if available
            if "query_explanation" in ai_result:
                assistant_message += f"\n\n{ai_result['query_explanation']}"
                with st.expander("Query Explanation", expanded=False):
                    st.markdown(ai_result["query_explanation"])
            
            # Add answer if available
            if "answer" in ai_result:
                with st.expander("AI Answer", expanded=False):
                    st.markdown(f"<div class='result-box'>{ai_result.get('answer', '')}</div>", unsafe_allow_html=True)
                    
                # Add to assistant message
                assistant_message += f"\n\nBased on the data: {ai_result.get('answer', '')}"
                
            # Add assistant message to conversation
            sql_query = ai_result.get('sql_query', '')
            assistant_message_id = conversation_store.add_message(
                st.session_state.conversation_id,
                "assistant",
                assistant_message,
                {"sql": sql_query, "generated": True}
            )
            
            # Display the SQL query
            with st.expander("Generated SQL", expanded=False):
                st.code(sql_query, language="sql")
            
            # Execute the query
            if sql_query:
                status_code, result = execute_sql_query(sql_query)
                display_query_results(status_code, result, sql_query, assistant_message_id)
            
        else:
            # Handle generation failure
            st.error("Failed to generate SQL for your question. Please try a different question.")
            
            # Add failure message to conversation
            conversation_store.add_message(
                st.session_state.conversation_id,
                "assistant",
                "I couldn't generate a SQL query for your question. Could you please rephrase or try a different question?",
                {"error": "SQL generation failed"}
            )
    


# Footer
st.markdown("---")
st.markdown("Smart Query Assistant | Built for Insurance Analytics")