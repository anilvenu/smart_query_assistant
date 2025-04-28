import psycopg2
import psycopg2.extras
import pandas as pd
import logging
from typing import Dict, List, Any, Tuple, Optional, Union
import json
import time

class DBHelper:
    """Helper class for PostgreSQL database operations."""
    
    def __init__(self, db_config: Dict[str, str], application_db: bool = False):
        """
        Initialize the database helper.
        
        Args:
            db_config: Database connection parameters
            application_db: Whether this helper connects to the application database
        """
        self.db_config = db_config.copy()
        self.connection = None
        self.application_db = application_db
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> psycopg2.extensions.connection:
        """
        Connect to the PostgreSQL database.
        
        Returns:
            Database connection object
        """
        if self.connection is None or self.connection.closed:
            try:
                self.connection = psycopg2.connect(**self.db_config)
                self.logger.info(f"Connected to database: {self.db_config['dbname']}")
            except Exception as e:
                self.logger.error(f"Error connecting to database: {str(e)}")
                raise
        
        return self.connection
    
    def close(self) -> None:
        """Close the database connection."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.connection = None
            self.logger.info("Database connection closed")
    
    def execute_query(self, 
                      query: str, 
                      params: Optional[Union[tuple, dict, list]] = None, 
                      fetch: bool = True,
                      commit: bool = False) -> Tuple[bool, Union[pd.DataFrame, List[Dict], int, str]]:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters for prepared statements
            fetch: Whether to fetch results (True for SELECT queries)
            commit: Whether to commit transaction (True for INSERT/UPDATE/DELETE)
            
        Returns:
            Tuple of (success, result)
            - If success is True and fetch is True, result is a pandas DataFrame
            - If success is True and fetch is False, result is row count (int)
            - If success is False, result is an error message (str)
        """
        conn = self.connect()
        cursor = None
        start_time = time.time()
        
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, params)
            
            execution_time = int((time.time() - start_time) * 1000)  # ms
            self.logger.debug(f"Query executed in {execution_time}ms")
            
            if fetch:
                # For SELECT queries
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                # Create DataFrame
                df = pd.DataFrame(rows, columns=columns)
                
                if commit:
                    conn.commit()
                
                return True, df
            else:
                # For INSERT/UPDATE/DELETE queries
                row_count = cursor.rowcount
                
                if commit:
                    conn.commit()
                
                return True, row_count
        
        except Exception as e:
            if conn:
                conn.rollback()
            
            error_msg = f"Query execution error: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        
        finally:
            if cursor:
                cursor.close()
    
    def execute_batch(self, 
                     query: str, 
                     params_list: List[Union[tuple, dict]],
                     commit: bool = True) -> Tuple[bool, Union[int, str]]:
        """
        Execute a batch operation with multiple parameter sets.
        
        Args:
            query: SQL query template
            params_list: List of parameter sets
            commit: Whether to commit the transaction
            
        Returns:
            Tuple of (success, result)
            - If success is True, result is the number of affected rows (int)
            - If success is False, result is an error message (str)
        """
        conn = self.connect()
        cursor = None
        
        try:
            cursor = conn.cursor()
            psycopg2.extras.execute_batch(cursor, query, params_list)
            
            if commit:
                conn.commit()
            
            return True, cursor.rowcount
        
        except Exception as e:
            if conn:
                conn.rollback()
            
            error_msg = f"Batch execution error: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        
        finally:
            if cursor:
                cursor.close()
    
    def transaction(self) -> psycopg2.extensions.connection:
        """
        Begin a transaction and return the connection.
        
        Use with 'with' statement for automatic commit/rollback.
        
        Returns:
            Database connection with transaction
        """
        return self.connect()
    
    def get_tables(self) -> List[str]:
        """
        Get list of tables in the database.
        
        Returns:
            List of table names
        """
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
        
        success, result = self.execute_query(query)
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            return result['table_name'].tolist()
        
        return []
    
    def get_schema_info(self) -> str:
        """
        Get detailed schema information for all tables.
        
        Returns:
            Formatted schema information string
        """
        tables = self.get_tables()
        schema_text = ""
        
        for table in tables:
            # Get column information
            query = f"""
            SELECT 
                column_name, 
                data_type,
                is_nullable,
                column_default
            FROM 
                information_schema.columns 
            WHERE 
                table_schema = 'public' 
                AND table_name = %s
            ORDER BY 
                ordinal_position
            """
            
            success, result = self.execute_query(query, (table,))
            
            if success and isinstance(result, pd.DataFrame) and not result.empty:
                schema_text += f"\nTABLE: {table}\n"
                
                for _, row in result.iterrows():
                    nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {row['column_default']}" if row['column_default'] else ""
                    schema_text += f"  - {row['column_name']} ({row['data_type']}, {nullable}{default})\n"
        
        return schema_text
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if the table exists, False otherwise
        """
        query = """
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
        """
        
        success, result = self.execute_query(query, (table_name,))
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            return result.iloc[0, 0]
        
        return False
    
    def get_row_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Number of rows in the table, or -1 on error
        """
        if not self.table_exists(table_name):
            return -1
        
        query = f"SELECT COUNT(*) FROM {table_name}"
        success, result = self.execute_query(query)
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            return result.iloc[0, 0]
        
        return -1