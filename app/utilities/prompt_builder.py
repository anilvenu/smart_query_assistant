"""
Prompt Builder Utility

This module provides functions for building prompts from templates stored in the database.
"""
import logging
import json
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Configure logging
logger = logging.getLogger(__name__)

class PromptBuilder:
    """Utility class for building prompts from templates stored in the database."""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize the PromptBuilder with a database connection.
        
        Args:
            db_connection_string: Database connection string
        """
        self.engine = create_engine(db_connection_string)
        self.Session = sessionmaker(bind=self.engine)
        
        # Cache for prompts
        self._prompt_cache = {}
    
    def get_prompt(self, prompt_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Get a prompt template from the database.
        
        Args:
            prompt_id: ID of the prompt to retrieve
            db: Database session (optional)
            
        Returns:
            Prompt template dictionary or None if not found
        """
        # Check cache first
        if prompt_id in self._prompt_cache:
            return self._prompt_cache[prompt_id]
        
        # Use provided session or create a new one
        session_provided = db is not None
        if not session_provided:
            db = self.Session()
        
        try:
            # Get prompt from database
            prompt_result = db.execute(
                text("SELECT * FROM prompts WHERE id = :id"),
                {"id": prompt_id}
            ).fetchone()
            
            if not prompt_result:
                logger.warning(f"Prompt not found: {prompt_id}")
                return None
            
            # Convert to dictionary
            prompt_dict = dict(prompt_result)
            
            # Get parameters for this prompt
            params_result = db.execute(
                text("SELECT * FROM prompt_parameters WHERE prompt_id = :prompt_id"),
                {"prompt_id": prompt_id}
            ).fetchall()
            
            # Add parameters to prompt dictionary
            prompt_dict['parameters'] = [dict(param) for param in params_result]
            
            # Cache the prompt
            self._prompt_cache[prompt_id] = prompt_dict
            
            return prompt_dict
            
        finally:
            # Close session if we created it
            if not session_provided:
                db.close()
    
    def build_prompt(self, prompt_id: str, params: Dict[str, Any], db: Optional[Session] = None) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Build a prompt from a template, substituting parameters.
        
        Args:
            prompt_id: ID of the prompt template to use
            params: Dictionary of parameter values to substitute
            db: Database session (optional)
            
        Returns:
            Tuple of (system_prompt, user_prompt, verbose_flag) or (None, None, False) if not found
        """
        prompt_template = self.get_prompt(prompt_id, db)
        
        if not prompt_template:
            logger.error(f"Cannot build prompt: Template '{prompt_id}' not found")
            return None, None, False
        
        verbose_flag = prompt_template.get('verbose_flag', False)
        
        if verbose_flag:
            logger.info(f"Building prompt: {prompt_id}")
            logger.info(f"Parameters: {json.dumps(params, default=str)}")
        
        # Check for required parameters
        for param in prompt_template.get('parameters', []):
            param_name = param['param_name']
            if param['required'] and param_name not in params:
                # Check if there's a default value
                if param.get('default_value') is not None:
                    # Use default value
                    if verbose_flag:
                        logger.info(f"Using default value for parameter '{param_name}': {param['default_value']}")
                    
                    # Try to evaluate default value if it looks like a literal
                    try:
                        if param['default_value'].startswith('{') or param['default_value'].startswith('['):
                            params[param_name] = eval(param['default_value'])
                        else:
                            params[param_name] = param['default_value']
                    except:
                        params[param_name] = param['default_value']
                else:
                    logger.error(f"Missing required parameter: {param_name}")
                    return None, None, False
        
        try:
            # Format the prompts with parameters
            system_prompt = prompt_template['system_prompt']
            
            # For the user prompt, we need to format it with care to handle f-string expressions
            user_prompt = prompt_template['user_prompt']
            
            # Simple formatting doesn't work well with complex f-string expressions
            # We'll use a safer but less complete approach
            try:
                user_prompt_formatted = user_prompt.format(**params)
            except KeyError as e:
                logger.error(f"Missing parameter in user prompt: {e}")
                logger.error(f"Available parameters: {list(params.keys())}")
                return None, None, False
            except Exception as e:
                logger.error(f"Error formatting user prompt: {e}")
                return None, None, False
            
            if verbose_flag:
                logger.info(f"Formatted system prompt: {system_prompt}")
                logger.info(f"Formatted user prompt: {user_prompt_formatted}")
            
            return system_prompt, user_prompt_formatted, verbose_flag
            
        except Exception as e:
            logger.error(f"Error building prompt: {e}")
            return None, None, False
    
    def clear_cache(self):
        """Clear the prompt cache."""
        self._prompt_cache = {}

# Create a singleton instance
prompt_builder = None

def initialize(db_connection_string: str):
    """
    Initialize the prompt builder with a database connection.
    
    Args:
        db_connection_string: Database connection string
    """
    global prompt_builder
    prompt_builder = PromptBuilder(db_connection_string)

def build_prompt(prompt_id: str, params: Dict[str, Any], db: Optional[Session] = None) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Build a prompt from a template, substituting parameters.
    
    Args:
        prompt_id: ID of the prompt template to use
        params: Dictionary of parameter values to substitute
        db: Database session (optional)
        
    Returns:
        Tuple of (system_prompt, user_prompt, verbose_flag) or (None, None, False) if not found
    """
    if prompt_builder is None:
        raise RuntimeError("Prompt builder not initialized. Call initialize() first.")
    
    return prompt_builder.build_prompt(prompt_id, params, db)