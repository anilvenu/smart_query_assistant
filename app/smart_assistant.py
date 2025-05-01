import yaml
import json
import os
import logging
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime


class SmartAssistant:
    """Class encapsulating SQL query assistant functionality."""
    
    def __init__(self, 
                 llm_service,
                 business_db_helper=None, 
                 application_db_helper=None,
                 conversation_store=None,
                 yaml_file_path="verified_queries.yaml",
                 debug_mode=False):
        """
        Initialize the SmartAssistant.
        
        Args:
            llm_service: LLM service for text generation and matching
            business_db_helper: Database helper for business data queries (optional)
            application_db_helper: Database helper for application data (optional)
            conversation_store: Conversation storage manager (optional)
            yaml_file_path: Path to the verified queries YAML file
            debug_mode: Whether to enable debug logging
        """
        # Configure logging
        self.logger = logging.getLogger()
        log_level = logging.DEBUG if debug_mode else logging.INFO
        self.logger.setLevel(log_level)
        
        # Add console handler if not already added
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Store dependencies
        self.llm_service = llm_service
        self.business_db = business_db_helper
        self.application_db = application_db_helper
        self.conversation_store = conversation_store
        self.yaml_file_path = yaml_file_path
        self.debug_mode = debug_mode
        
        # Load verified queries on initialization
        self.verified_queries = self.load_verified_queries()
        self.logger.info(f"Loaded {len(self.verified_queries)} verified queries")
        
        # Store database schema info if available
        self.schema_info = self.get_database_schema() if self.business_db else None
    
    def load_verified_queries(self) -> List[Dict[str, Any]]:
        """
        Load verified queries from YAML file.
        
        Returns:
            List of verified query dictionaries
        """
        try:
            if os.path.exists(self.yaml_file_path):
                with open(self.yaml_file_path, 'r') as file:
                    data = yaml.safe_load(file)
                    queries = data.get('verified_queries', []) if data else []
                    self.logger.info(f"Loaded {len(queries)} verified queries from {self.yaml_file_path}")
                    return queries
            else:
                self.logger.warning(f"YAML file not found: {self.yaml_file_path}")
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error loading queries: {str(e)}")
        
        return []
    
    def get_database_schema(self) -> str:
        """
        Get database schema information if available.
        
        Returns:
            Schema information string or None if not available
        """
        if not self.business_db:
            self.logger.warning("No business database helper available")
            return None
        
        try:
            schema_info = self.business_db.get_schema_info()
            return schema_info
        except Exception as e:
            self.logger.error(f"Error getting database schema: {str(e)}")
            return None
    
    def find_matching_query(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Find a matching verified query for the given question.
        
        Args:
            question: Natural language question
        
        Returns:
            Dictionary with matching information or None if no match
        """
        if not self.verified_queries:
            self.logger.warning("No verified queries available")
            return None
        
        # Create a string representation of all verified queries
        queries_str = ""
        for i, query in enumerate(self.verified_queries):
            queries_str += f"Query {i+1}:\n"
            queries_str += f"Name: {query.get('name', '')}\n"
            queries_str += f"Question: {query.get('question', '')}\n"
            queries_str += f"SQL: {query.get('sql', '')}\n"
            queries_str += f"Explanation: {query.get('query_explanation', '')}\n\n"
        
        self.logger.info(f"Created prompt with {len(self.verified_queries)} queries")
        
        if self.debug_mode:
            self.logger.debug(f"Full queries text: {queries_str}")
        
        # System prompt for query matching
        system_prompt = """You are an expert at matching user questions with verified SQL queries.
Your task is to analyze the user's question and find the most similar verified query."""

        # User prompt with matching rules
        user_prompt = f"""Follow these comparison rules carefully:
1. Core Query Components:
   - What is being counted/summed/averaged?
   - Which time period is being queried?
   - What status or category filters are needed?

2. Pattern Matching:
   - Match main action (count, sum, etc.)
   - Match time period (specific year)
   - Match status (active, inactive, etc.)
   - Look for status values in SQL comments

3. Modification Requirements:
   - List ALL required changes in modifications
   - Include both year AND status changes when needed
   - Be explicit about which status value to use
   - Use values from SQL comments when available

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

User Question: {question}

Previously verified queries:
{queries_str}
"""
        
        try:
            self.logger.info("Sending request to LLM service...")
            
            # Get structured response from LLM
            response_json = self.llm_service.generate_structured_output(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )
            
            self.logger.info("Received response from LLM service")
            
            if self.debug_mode:
                self.logger.debug(f"Raw LLM response: {json.dumps(response_json, indent=2)}")
            
            # Validate response format
            required_keys = {"match", "query_number", "similarity", "modification_needed", "modifications"}
            if not all(key in response_json for key in required_keys):
                self.logger.error(f"Missing required keys in response. Found keys: {list(response_json.keys())}")
                return None
            
            if not response_json["match"]:
                self.logger.info("No match found by LLM")
                return None
            
            query_number = int(response_json["query_number"])
            if not (0 < query_number <= len(self.verified_queries)):
                self.logger.error(f"Invalid query number: {query_number}")
                return None
            
            self.logger.info(f"Match found! Query #{query_number} with {response_json['similarity']}% similarity")
            
            return {
                "verified_query": self.verified_queries[query_number - 1],
                "similarity": response_json["similarity"],
                "modification_needed": response_json["modification_needed"],
                "modifications": response_json["modifications"]
            }
        except Exception as e:
            self.logger.error(f"Error during query matching: {str(e)}", exc_info=True)
            return None
    
    def adjust_sql(self, original_sql: str, modifications: str) -> str:
        """
        Adjust SQL based on modification instructions.
        
        Args:
            original_sql: Original SQL query
            modifications: Modification instructions
            
        Returns:
            Modified SQL query
        """
        if not modifications:
            return original_sql
        

        system_prompt = """You are an expert SQL developer for PostgreSQL. 
Your task is to analyze and modify SQL based on specific requirements."""
        
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

Return only the modified SQL query.
"""
        
        try:
            self.logger.info("Adjusting SQL query")
            
            # Get modified SQL from LLM
            modified_sql = self.llm_service.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0
            )
            
            return modified_sql.strip()
        except Exception as e:
            self.logger.error(f"Error adjusting SQL: {str(e)}")
            return original_sql
    
    def generate_sql(self, question: str) -> Dict[str, Any]:
        """
        Generate SQL for a question using LLM.
        
        Args:
            question: Natural language question
            
        Returns:
            Dictionary with SQL and explanation
        """
        # System prompt for SQL generation
        system_prompt = """You are an expert SQL developer for PostgreSQL. 
Your task is to generate an optimized SQL query based on a natural language question and the given database schema."""
        
        # User prompt with schema and question
        schema_context = self.schema_info if self.schema_info else "No schema information available."
        
        user_prompt = f"""Database Schema:
{schema_context}

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
            self.logger.info("Generating SQL")
            
            # Get response from LLM
            response_json = self.llm_service.generate_structured_output(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )
            
            return response_json
        except Exception as e:
            self.logger.error(f"Error generating SQL: {str(e)}")
            return {}
    
    def execute_query(self, sql: str) -> Tuple[int, Dict[str, Any]]:
        """
        Execute SQL query if database helper is available.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Tuple of (status_code, result)
        """
        if not self.business_db:
            self.logger.warning("No business database helper available")
            return 500, {"error": "Database not available"}
        
        try:
            start_time = datetime.now()
            
            # Execute query using business database helper
            success, result = self.business_db.execute_query(sql)
            
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            if success and isinstance(result, pd.DataFrame):
                # Format for compatibility
                return 200, {
                    "rows": result.to_dict('records'),
                    "columnNames": result.columns.tolist(),
                    "execution_time_ms": execution_time_ms,
                    "row_count": len(result)
                }
            else:
                # Error case
                return 500, {"error": str(result)}
                
        except Exception as e:
            self.logger.error(f"Query execution error: {str(e)}", exc_info=True)
            return 500, {"error": str(e)}
    
    def process_question(self, question: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Process a question and generate a response.
        
        Args:
            question: Natural language question
            conversation_id: Optional conversation ID for storage
            
        Returns:
            Dictionary with response information
        """
        self.logger.info(f"Processing question: {question}")
        
        # Validate and refine question
        # TODO

        # Store user message if conversation store
        user_message_id = None
        if self.conversation_store and conversation_id:
            user_message_id = self.conversation_store.add_message(
                conversation_id, 
                "user", 
                question
            )
        
        # Find a matching verified query and recommended modifications 
        # TODO: Split into match followed by recommendation - 2 steps
        match_info = self.find_matching_query(question)
        
        if match_info:
            verified_query = match_info["verified_query"]
            self.logger.info(f"Found matching query: {verified_query.get('name')} with {match_info['similarity']}% similarity")
            
            # Get the SQL from the verified query
            sql = verified_query.get("sql", "")
            
            # Check if modifications are needed
            if match_info.get("modification_needed", False):
                self.logger.info(f"Modifications needed: {match_info.get('modifications', '')}")
                self.logger.info(f"Original SQL: \n{sql}")

                # Adjust the SQL based on the modifications
                sql = self.adjust_sql(sql, match_info.get("modifications", ""))
                self.logger.info(f"Adjusted SQL: \n{sql}")
            else:
                self.logger.info("No modifications needed for the SQL")
            
            # Prepare response information
            # TODO: Use Pydantic model for response structure

            response = {
                "match_found": True,
                "verified_query": verified_query,
                "similarity": match_info.get("similarity"),
                "modification_needed": match_info.get("modification_needed", False),
                "modifications": match_info.get("modifications", ""),
                "sql": sql,
                "source": "verified"
            }
            
            # Execute the query if database is available
            if self.business_db:
                status_code, result = self.execute_query(sql)
                response["execution"] = {
                    "status_code": status_code,
                    "result": result
                }
            
            # Store assistant message if conversation store is available
            if self.conversation_store and conversation_id and user_message_id:
                # Prepare message content
                content = f"I found a relevant query for '{verified_query.get('name', 'your question')}'."
                
                if match_info.get("modification_needed", False):
                    content += f"\n\nI needed to make some adjustments: {match_info.get('modifications', '')}"
                
                if verified_query.get("query_explanation"):
                    content += f"\n\n{verified_query['query_explanation']}"
                
                # Add assistant message
                assistant_message_id = self.conversation_store.add_message(
                    conversation_id,
                    "assistant",
                    content,
                    {"sql": sql, "verified_query_name": verified_query.get("name")}
                )
                
                # Record query execution if available
                if "execution" in response and self.conversation_store:
                    execution = response["execution"]
                    if execution["status_code"] == 200:
                        self.conversation_store.add_query_execution(
                            message_id=assistant_message_id,
                            sql_query=sql,
                            status="success",
                            execution_time_ms=execution["result"].get("execution_time_ms"),
                            row_count=execution["result"].get("row_count")
                        )
                    else:
                        self.conversation_store.add_query_execution(
                            message_id=assistant_message_id,
                            sql_query=sql,
                            status="error",
                            error_message=execution["result"].get("error")
                        )
            
            return response
            
        else:
            # No match found, generate SQL using LLM
            self.logger.info("No matching query found, generating SQL with LLM")
            
            # Generate SQL
            ai_result = self.generate_sql(question)
            
            if not ai_result:
                self.logger.error("Failed to generate SQL")
                return {
                    "match_found": False,
                    "error": "Failed to generate SQL"
                }
            
            # Get SQL from result
            sql_query = ai_result.get('sql_query', '')
            
            # Prepare response
            response = {
                "match_found": False,
                "ai_generated": ai_result,
                "sql": sql_query,
                "source": "ai_generated"
            }
            
            # Execute the query if available
            if self.business_db and sql_query:
                status_code, result = self.execute_query(sql_query)
                response["execution"] = {
                    "status_code": status_code,
                    "result": result
                }
            
            # Store assistant message if conversation store is available
            if self.conversation_store and conversation_id and user_message_id:
                # Prepare message content
                content = "I've generated a new SQL query to answer your question."
                
                if "query_explanation" in ai_result:
                    content += f"\n\n{ai_result['query_explanation']}"
                
                if "answer" in ai_result:
                    content += f"\n\nBased on the data: {ai_result.get('answer', '')}"
                
                # Add assistant message
                assistant_message_id = self.conversation_store.add_message(
                    conversation_id,
                    "assistant",
                    content,
                    {"sql": sql_query, "generated": True}
                )
                
                # Record query execution if available
                if "execution" in response and self.conversation_store:
                    execution = response["execution"]
                    if execution["status_code"] == 200:
                        self.conversation_store.add_query_execution(
                            message_id=assistant_message_id,
                            sql_query=sql_query,
                            status="success",
                            execution_time_ms=execution["result"].get("execution_time_ms"),
                            row_count=execution["result"].get("row_count")
                        )
                    else:
                        self.conversation_store.add_query_execution(
                            message_id=assistant_message_id,
                            sql_query=sql_query,
                            status="error",
                            error_message=execution["result"].get("error")
                        )
            
            return response