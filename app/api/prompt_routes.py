# Import necessary modules
import logging
import traceback
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)

# Import the get_db_session function from your existing code
from app.helper import get_db_session

# Import LLM service for testing prompts
from app.llm.llm_service import LLMService

# Create a router for prompt management
router = APIRouter(prefix="/api/prompts", tags=["Prompts"])

# Models for request and response
class PromptParameter(BaseModel):
    id: Optional[int] = None
    param_name: str
    description: str
    default_value: Optional[str] = None
    required: bool = True

class PromptCreate(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    user_prompt: str
    verbose_flag: bool = False
    parameters: List[PromptParameter]

class PromptResponse(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    user_prompt: str
    verbose_flag: bool
    created_at: datetime
    updated_at: datetime
    parameters: List[PromptParameter]

class TestPromptRequest(BaseModel):
    prompt_id: str
    parameters: Dict[str, Any]

# API endpoints
@router.get("", response_model=List[Dict[str, Any]])
async def get_prompts(db: Session = Depends(get_db_session)):
    """Get all prompts"""
    try:
        # Query prompts
        query = """
        SELECT id, name, description, verbose_flag as verbose_flag, created_at, updated_at 
        FROM prompts 
        ORDER BY name
        """
        result = db.execute(text(query))
        
        # Convert to list of dictionaries properly
        # First get the column names
        columns = result.keys()
        
        # Then create dictionaries with column names as keys
        prompts = []
        for row in result:
            # Create dictionary from row using column names
            prompt_dict = {}
            for i, column in enumerate(columns):
                prompt_dict[column] = row[i]
            prompts.append(prompt_dict)
        
        logger.debug(f"Found {len(prompts)} prompts")
        
        # Count parameters for each prompt
        for prompt in prompts:
            param_count = db.execute(
                text("SELECT COUNT(*) FROM prompt_parameters WHERE prompt_id = :id"),
                {"id": prompt["id"]}
            ).scalar()
            prompt["parameter_count"] = param_count
        
        return prompts
    except Exception as e:
        # Get full traceback
        error_details = traceback.format_exc()
        
        # Log the detailed error
        logger.error(f"Failed to fetch prompts: {str(e)}")
        logger.error(f"Traceback: {error_details}")
        
        # Return a more user-friendly error
        raise HTTPException(
            status_code=500, 
            detail={
                "message": "Failed to fetch prompts from database",
                "error": str(e),
                "error_details": error_details if not isinstance(e, HTTPException) else None
            }
        )

@router.get("/{prompt_id}", response_model=Dict[str, Any])
async def get_prompt(prompt_id: str, db: Session = Depends(get_db_session)):
    """Get a specific prompt by ID"""
    try:
        # Query prompt
        query = """
        SELECT id, name, description, system_prompt, user_prompt, verbose_flag, created_at, updated_at 
        FROM prompts 
        WHERE id = :id
        """
        result = db.execute(text(query), {"id": prompt_id}).fetchone()
        
        if not result:            
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Convert to dictionary
        prompt = {}
        columns = ["id", "name", "description", "system_prompt", "user_prompt", "verbose_flag", "created_at", "updated_at"]
        for i, column in enumerate(columns):
            prompt[column] = result[i]
        
        # Get parameters
        params_query = """
        SELECT id, param_name, description, default_value, required 
        FROM prompt_parameters 
        WHERE prompt_id = :id 
        ORDER BY id
        """
        params_result = db.execute(text(params_query), {"id": prompt_id})
        
        # Add parameters to prompt
        parameters = []
        param_columns = ["id", "param_name", "description", "default_value", "required"]
        for row in params_result:
            param = {}
            for i, column in enumerate(param_columns):
                param[column] = row[i]
            parameters.append(param)
        
        prompt["parameters"] = parameters
        
        return prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch prompt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt: {str(e)}")

@router.post("", response_model=Dict[str, Any])
async def create_prompt(prompt: PromptCreate, db: Session = Depends(get_db_session)):
    """Create a new prompt"""
    try:
        # Check if prompt ID already exists
        exists = db.execute(
            text("SELECT id FROM prompts WHERE id = :id"),
            {"id": prompt.id}
        ).fetchone()
        
        if exists:
            raise HTTPException(status_code=400, detail="Prompt ID already exists")
        
        # Insert prompt
        db.execute(
            text("""
            INSERT INTO prompts (id, name, description, system_prompt, user_prompt, verbose_flag)
            VALUES (:id, :name, :description, :system_prompt, :user_prompt, :verbose_flag)
            """),
            {
                "id": prompt.id,
                "name": prompt.name,
                "description": prompt.description,
                "system_prompt": prompt.system_prompt,
                "user_prompt": prompt.user_prompt,
                "verbose_flag": prompt.verbose_flag
            }
        )
        
        # Insert parameters
        for param in prompt.parameters:
            db.execute(
                text("""
                INSERT INTO prompt_parameters (prompt_id, param_name, description, default_value, required)
                VALUES (:prompt_id, :param_name, :description, :default_value, :required)
                """),
                {
                    "prompt_id": prompt.id,
                    "param_name": param.param_name,
                    "description": param.description,
                    "default_value": param.default_value,
                    "required": param.required
                }
            )
        
        # Commit transaction
        db.commit()
        
        return {"status": "success", "id": prompt.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create prompt: {str(e)}")

@router.put("/{prompt_id}", response_model=Dict[str, Any])
async def update_prompt(prompt_id: str, prompt: PromptCreate, db: Session = Depends(get_db_session)):
    """Update an existing prompt"""
    try:
        # Check if prompt exists
        exists = db.execute(
            text("SELECT id FROM prompts WHERE id = :id"),
            {"id": prompt_id}
        ).fetchone()
        
        if not exists:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Verify IDs match
        if prompt_id != prompt.id:
            raise HTTPException(status_code=400, detail="Prompt ID mismatch")
        
        # Update prompt
        db.execute(
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
                "id": prompt.id,
                "name": prompt.name,
                "description": prompt.description,
                "system_prompt": prompt.system_prompt,
                "user_prompt": prompt.user_prompt,
                "verbose_flag": prompt.verbose_flag
            }
        )
        
        # Delete existing parameters
        db.execute(
            text("DELETE FROM prompt_parameters WHERE prompt_id = :prompt_id"),
            {"prompt_id": prompt.id}
        )
        
        # Insert new parameters
        for param in prompt.parameters:
            db.execute(
                text("""
                INSERT INTO prompt_parameters (prompt_id, param_name, description, default_value, required)
                VALUES (:prompt_id, :param_name, :description, :default_value, :required)
                """),
                {
                    "prompt_id": prompt.id,
                    "param_name": param.param_name,
                    "description": param.description,
                    "default_value": param.default_value,
                    "required": param.required
                }
            )
        
        # Commit transaction
        db.commit()
        
        return {"status": "success", "id": prompt.id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update prompt: {str(e)}")

@router.delete("/{prompt_id}", response_model=Dict[str, Any])
async def delete_prompt(prompt_id: str, db: Session = Depends(get_db_session)):
    """Delete a prompt"""
    try:
        # Check if prompt exists
        exists = db.execute(
            text("SELECT id FROM prompts WHERE id = :id"),
            {"id": prompt_id}
        ).fetchone()
        
        if not exists:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Delete parameters first (cascading should handle this, but being explicit)
        db.execute(
            text("DELETE FROM prompt_parameters WHERE prompt_id = :prompt_id"),
            {"prompt_id": prompt_id}
        )
        
        # Delete prompt
        db.execute(
            text("DELETE FROM prompts WHERE id = :id"),
            {"id": prompt_id}
        )
        
        # Commit transaction
        db.commit()
        
        return {"status": "success", "id": prompt_id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete prompt: {str(e)}")

@router.post("/test", response_model=Dict[str, Any])
async def test_prompt(request: TestPromptRequest, db: Session = Depends(get_db_session)):
    """Test a prompt with parameters"""
    try:
        # Initialize LLM service
        llm_service = LLMService()
        
        # Get prompt from database
        prompt_query = """
        SELECT system_prompt, user_prompt, verbose_flag
        FROM prompts 
        WHERE id = :id
        """
        prompt_result = db.execute(text(prompt_query), {"id": request.prompt_id}).fetchone()
        
        if not prompt_result:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        system_prompt = prompt_result[0]
        user_prompt = prompt_result[1]
        verbose_flag = prompt_result[2]
        
        # Get parameters
        params_query = """
        SELECT param_name, required, default_value
        FROM prompt_parameters 
        WHERE prompt_id = :id
        """
        params_result = db.execute(text(params_query), {"id": request.prompt_id})
        
        # Validate parameters
        for param in params_result:
            param_name = param[0]
            required = param[1]
            default_value = param[2]
            
            if required and param_name not in request.parameters and default_value is None:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required parameter: {param_name}"
                )
            
            # Use default value if parameter not provided
            if param_name not in request.parameters and default_value is not None:
                try:
                    # Try to evaluate default value if it's JSON-like
                    if default_value.startswith('{') or default_value.startswith('['):
                        request.parameters[param_name] = json.loads(default_value)
                    else:
                        request.parameters[param_name] = default_value
                except:
                    request.parameters[param_name] = default_value
        
        # Format the user prompt
        try:
            formatted_user_prompt = user_prompt.format(**request.parameters)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing parameter in user prompt: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error formatting user prompt: {str(e)}")
        
        # Call LLM service
        try:
            # Decide which function to call based on return type expected
            # For simplicity, assume we want structured output if the prompt ID contains 'json'
            want_structured = 'json' in request.prompt_id.lower() or formatted_user_prompt.lower().count('json') > 2
            
            if want_structured:
                result = llm_service.generate_structured_output(
                    prompt=formatted_user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.1
                )
            else:
                result = llm_service.generate_text(
                    prompt=formatted_user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.1
                )
                
            # Return results
            return {
                "status": "success",
                "result": result,
                "formatted_prompt": {
                    "system_prompt": system_prompt,
                    "user_prompt": formatted_user_prompt
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error calling LLM service: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test prompt: {str(e)}")

# Function to add these routes to the main app
def add_prompt_routes(app):
    app.include_router(router)