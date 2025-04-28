import uuid
import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from .db_helper import DBHelper
import pandas as pd

class ConversationStore:
    """Manages conversation data in the application database."""
    
    def __init__(self, db_helper: DBHelper):
        """
        Initialize the conversation store.
        
        Args:
            db_helper: Database helper for the application database
        """
        if not db_helper.application_db:
            raise ValueError("ConversationStore requires a DBHelper connected to the application database")
        
        self.db_helper = db_helper
        self.logger = logging.getLogger(__name__)
    
    def create_conversation(self, title: str = "New Conversation") -> str:
        """
        Create a new conversation.
        
        Args:
            title: Conversation title
            
        Returns:
            Conversation ID, or None on error
        """
        conversation_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO conversations (conversation_id, title)
        VALUES (%s, %s)
        RETURNING conversation_id
        """
        
        success, result = self.db_helper.execute_query(
            query, 
            (conversation_id, title),
            commit=True
        )
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            self.logger.info(f"Created conversation: {conversation_id}")
            return conversation_id
        
        self.logger.error(f"Failed to create conversation")
        return None
    
    def add_message(self, 
                   conversation_id: str, 
                   role: str, 
                   content: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Conversation ID
            role: Message role (user, assistant)
            content: Message content
            metadata: Optional metadata dictionary
            
        Returns:
            Message ID, or None on error
        """
        message_id = str(uuid.uuid4())
        
        # Convert metadata to JSON
        metadata_json = json.dumps(metadata) if metadata else None
        
        query = """
        INSERT INTO messages (message_id, conversation_id, role, content, metadata)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING message_id
        """
        
        success, result = self.db_helper.execute_query(
            query, 
            (message_id, conversation_id, role, content, metadata_json),
            commit=True
        )
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            self.logger.info(f"Added message {message_id} to conversation {conversation_id}")
            return message_id
        
        self.logger.error(f"Failed to add message to conversation {conversation_id}")
        return None
    
    def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        """
        Update a conversation's title.
        
        Args:
            conversation_id: Conversation ID
            title: New title
            
        Returns:
            Success status
        """
        query = """
        UPDATE conversations
        SET title = %s, updated_at = CURRENT_TIMESTAMP
        WHERE conversation_id = %s
        """
        
        success, result = self.db_helper.execute_query(
            query, 
            (title, conversation_id),
            fetch=False,
            commit=True
        )
        
        if success and isinstance(result, int) and result > 0:
            self.logger.info(f"Updated title for conversation {conversation_id}")
            return True
        
        self.logger.error(f"Failed to update title for conversation {conversation_id}")
        return False
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation details.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation details, or None if not found
        """
        query = """
        SELECT conversation_id, title, created_at, updated_at, status
        FROM conversations
        WHERE conversation_id = %s
        """
        
        success, result = self.db_helper.execute_query(query, (conversation_id,))
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            return result.iloc[0].to_dict()
        
        return None
    
    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List of message dictionaries
        """
        query = """
        SELECT message_id, role, content, created_at, metadata
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at
        """
        
        success, result = self.db_helper.execute_query(query, (conversation_id,))
        
        if success and isinstance(result, pd.DataFrame):
            # Convert DataFrame to list of dicts, parse metadata
            messages = []
            for _, row in result.iterrows():
                message = row.to_dict()
                
                # Parse metadata JSON if it's a string
                if message['metadata'] and isinstance(message['metadata'], str):
                    try:
                        message['metadata'] = json.loads(message['metadata'])
                    except json.JSONDecodeError:
                        message['metadata'] = {}
                elif message['metadata'] is None:
                    message['metadata'] = {}
                # Otherwise leave it as is - it might already be parsed
                
                messages.append(message)
            
            return messages
        
        return []
    
    def add_query_execution(self, 
                           message_id: str, 
                           sql_query: str, 
                           status: str, 
                           execution_time_ms: int = None,
                           row_count: int = None,
                           error_message: str = None) -> str:
        """
        Record a query execution.
        
        Args:
            message_id: Associated message ID
            sql_query: Executed SQL query
            status: Execution status (success, error)
            execution_time_ms: Query execution time in milliseconds
            row_count: Number of rows returned/affected
            error_message: Error message if status is error
            
        Returns:
            Execution ID, or None on error
        """
        execution_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO query_executions (
            execution_id, message_id, sql_query, status,
            execution_time_ms, row_count, error_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING execution_id
        """
        
        success, result = self.db_helper.execute_query(
            query, 
            (
                execution_id, message_id, sql_query, status,
                execution_time_ms, row_count, error_message
            ),
            commit=True
        )
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            self.logger.info(f"Recorded query execution: {execution_id}")
            return execution_id
        
        self.logger.error(f"Failed to record query execution")
        return None
    
    def add_visualization(self, 
                         message_id: str, 
                         visualization_type: str,
                         configuration: Dict[str, Any]) -> str:
        """
        Add a visualization to a message.
        
        Args:
            message_id: Associated message ID
            visualization_type: Type of visualization (bar_chart, pie_chart, etc.)
            configuration: Visualization configuration
            
        Returns:
            Visualization ID, or None on error
        """
        visualization_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO visualizations (
            visualization_id, message_id, visualization_type, configuration
        )
        VALUES (%s, %s, %s, %s)
        RETURNING visualization_id
        """
        
        # Convert configuration to JSON
        configuration_json = json.dumps(configuration)
        
        success, result = self.db_helper.execute_query(
            query, 
            (visualization_id, message_id, visualization_type, configuration_json),
            commit=True
        )
        
        if success and isinstance(result, pd.DataFrame) and not result.empty:
            self.logger.info(f"Added visualization: {visualization_id}")
            return visualization_id
        
        self.logger.error(f"Failed to add visualization")
        return None
    
    def get_visualizations(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Get all visualizations for a message.
        
        Args:
            message_id: Message ID
            
        Returns:
            List of visualization dictionaries
        """
        query = """
        SELECT visualization_id, visualization_type, configuration, created_at
        FROM visualizations
        WHERE message_id = %s
        ORDER BY created_at
        """
        
        success, result = self.db_helper.execute_query(query, (message_id,))
        
        if success and isinstance(result, pd.DataFrame):
            # Convert DataFrame to list of dicts, parse configuration
            visualizations = []
            for _, row in result.iterrows():
                visualization = row.to_dict()
                
                # Parse configuration JSON
                if visualization['configuration']:
                    try:
                        visualization['configuration'] = json.loads(visualization['configuration'])
                    except json.JSONDecodeError:
                        visualization['configuration'] = {}
                
                visualizations.append(visualization)
            
            return visualizations
        
        return []
    
    def get_conversations(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get a list of conversations.
        
        Args:
            limit: Maximum number of conversations to return
            offset: Offset for pagination
            
        Returns:
            List of conversation dictionaries
        """
        query = """
        SELECT 
            c.conversation_id, 
            c.title, 
            c.created_at, 
            c.updated_at,
            c.status,
            COUNT(m.message_id) AS message_count
        FROM 
            conversations c
            LEFT JOIN messages m ON c.conversation_id = m.conversation_id
        GROUP BY 
            c.conversation_id, c.title, c.created_at, c.updated_at, c.status
        ORDER BY 
            c.updated_at DESC
        LIMIT %s
        OFFSET %s
        """
        
        success, result = self.db_helper.execute_query(query, (limit, offset))
        
        if success and isinstance(result, pd.DataFrame):
            return result.to_dict('records')
        
        return []
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all associated data.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Success status
        """
        # Use a transaction to ensure all related data is deleted
        conn = self.db_helper.connect()
        
        try:
            with conn:
                with conn.cursor() as cursor:
                    # Delete messages (cascade will delete query_executions and visualizations)
                    cursor.execute(
                        "DELETE FROM conversations WHERE conversation_id = %s",
                        (conversation_id,)
                    )
                    
                    # Check if any rows were affected
                    if cursor.rowcount > 0:
                        self.logger.info(f"Deleted conversation: {conversation_id}")
                        return True
                    else:
                        self.logger.warning(f"No conversation found with ID: {conversation_id}")
                        return False
        except Exception as e:
            self.logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            return False