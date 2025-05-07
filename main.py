import traceback
import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
# Set exception hook to log uncaught exceptions with traceback
def log_uncaught_exceptions(exc_type, exc_value, exc_traceback):
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = log_uncaught_exceptions

# Fast API
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, Depends
from fastapi import Form, Body

from datetime import datetime

from pydantic import BaseModel
from typing import List, Dict, Optional, Any

import json

# For database connection
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.helper import (
    VerifiedQuery,
    Question,
    enhance_question,
    generate_intent_clarifications,
    get_best_query,
    get_query_recommendations,
    get_follow_up_queries,
    modify_query,
    review_modified_query
)
from app.helper import get_verified_query, get_verified_queries, save_verified_query, delete_verified_query, get_db_session
from app.helper import get_user_profile, set_user_profile, get_calendar_context

from app.agents.report_writer import (
    write_narrative
)
from app.gadgets.sql_runner import run_query
from app.visualization.chart_generator import generate_chart_config

# Configurations
from app.utilities import config

# LLM service
from app.llm.llm_service import LLMService

# Pydantic models for request bodies
class QuestionCreate(BaseModel):
    text: str

class VerifiedQueryCreate(BaseModel):
    id: str
    name: str
    query_explanation: str
    sql: str
    instructions: Optional[str] = None
    tables_used: List[str] = []
    questions: List[QuestionCreate] = []
    follow_ups: List[str] = []
    verified_by: str = "Admin"

# Configure database connections
engine = create_engine(config.APPLICATION_DB_CONNECTION_STRING)
insurance_db_engine = create_engine(config.BUSINESS_DB_CONNECTION_STRING)

# Initialize LLM service
llm_service = LLMService()

MAX_REVIEW_ITERATIONS = 3

# Add some sample context
#context = {
#    "calendar_context": "Current date: 2025-04-30, Current year: 2025, Previous year: 2024, Current quarter: 2025 Q2, Previous quarter: 2025 Q1, Current month: 2025-04, Previous month: 2025-03",
#    "user_profile": "Region: Northeast",
#}



app = FastAPI(
    title="Smart Query Assistant API",
    description="API for data analysis and query management",
    version="1.0.0",
    openapi_tags=[
        {"name": "Verified Queries", "description": "Operations with verified SQL queries"},
        {"name": "Query Execution", "description": "Run and analyze SQL queries"},
        {"name": "User Profiles", "description": "User profile management"},
        {"name": "Context", "description": "Calendar and context management"},
    ]
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

clients = set()

# Web pages
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin/verified_queries")
async def get_all_verified_queries(request: Request):
    """Admin page to view all verified queries"""
    return templates.TemplateResponse("admin/verified_queries.html", {"request": request})

@app.get("/admin/verified_query/{query_id}")
async def view_verified_query(request: Request, query_id: str):
    """Admin page to view a specific verified query"""
    return templates.TemplateResponse("admin/verified_query_detail.html", {"request": request, "query_id": query_id})

@app.get("/admin/verified_query/new")
async def new_verified_query_page(request: Request):
    """Admin page to create a new verified query"""
    return templates.TemplateResponse(
        "admin/verified_query_edit.html", 
        {"request": request, "is_new": True}
    )

@app.get("/admin/verified_query/{query_id}/edit")
async def edit_verified_query_page(request: Request, query_id: str):
    """Admin page to edit an existing verified query"""
    return templates.TemplateResponse(
        "admin/verified_query_edit.html", 
        {"request": request, "is_new": False, "query_id": query_id}
    )

# API endpoints
@app.get("/api/verified_queries", tags=["Verified Queries"])
async def api_get_verified_queries(db: Session = Depends(get_db_session)):
    """API endpoint to get all verified queries"""
    queries = get_verified_queries(db)
    return [q.model_dump(mode="json") for q in queries]

@app.get("/api/verified_query/{query_id}", tags=["Verified Queries"])
async def api_get_verified_query(query_id: str, db: Session = Depends(get_db_session)):
    """API endpoint to get a specific verified query"""
    query = get_verified_query(query_id, db, include_embeddings=False)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    return query.model_dump(mode="json")

@app.get("/api/find_matching_query", tags=["Verified Queries"])
async def api_find_matching_query(
    query_text: str,
    db: Session = Depends(get_db_session)
):
    """Find the best matching verified query for a given text"""
    try:
        # Use the same matching function used in Smart Query Assistant
        best_query_result = get_best_query(query_text, llm_service, db=db)
        
        if not best_query_result or not best_query_result.get("verified_query"):
            return {"found": False, "message": "No matching query found"}
        
        verified_query = best_query_result["verified_query"]
        confidence = best_query_result.get("confidence", 0)
        
        return {
            "found": True,
            "query": verified_query.model_dump(mode="json"),
            "confidence": confidence,
            "matched_question": best_query_result.get("matched_question", "")
        }
    except Exception as e:
        logger.error(f"Error finding matching query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error finding match: {str(e)}")


@app.get("/api/query_network", tags=["Verified Queries"])
async def api_get_query_network(db: Session = Depends(get_db_session)):
    """Get the network of verified queries for visualization"""
    try:
        # Get all verified queries
        queries = get_verified_queries(db)
        
        # Prepare nodes and links for the graph visualization
        nodes = []
        links = []
        
        # Create nodes
        for query in queries:
            # Extract essential data for each node
            nodes.append({
                "id": query.id,
                "name": query.name,
                "tables": query.tables_used,
                # Count questions for node size
                "questionCount": len(query.questions) if query.questions else 0
            })
            
            # Create links (edges)
            if query.follow_ups:
                for follow_up_id in query.follow_ups:
                    links.append({
                        "source": query.id,
                        "target": follow_up_id
                    })
        
        return {
            "nodes": nodes,
            "links": links
        }
    except Exception as e:
        logger.error(f"Error getting query network: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# API for creating/updating verified queries
@app.post("/api/verified_query", tags=["Verified Queries"])
async def api_create_verified_query(
    query: VerifiedQueryCreate,
    db: Session = Depends(get_db_session)
):
    """API endpoint to create a new verified query"""
    try:
        # Check if ID already exists
        existing = get_verified_query(query.id, db)
        if existing:
            raise HTTPException(status_code=400, detail="Query ID already exists")
        
        # Create VerifiedQuery object
        verified_query = VerifiedQuery(
            id=query.id,
            name=query.name,
            query_explanation=query.query_explanation,
            sql=query.sql,
            instructions=query.instructions,
            tables_used=query.tables_used,
            questions=[Question(text=q.text) for q in query.questions],
            follow_ups=query.follow_ups,
            verified_at=datetime.now(),
            verified_by=query.verified_by
        )
        
        # Save to database
        success = save_verified_query(verified_query, db)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save query")
        
        return {"status": "success", "id": query.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating verified query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.put("/api/verified_query/{query_id}", tags=["Verified Queries"])
async def api_update_verified_query(
    query_id: str,
    query: VerifiedQueryCreate,
    db: Session = Depends(get_db_session)
):
    """API endpoint to update an existing verified query"""
    try:
        # Check if ID exists
        existing = get_verified_query(query_id, db)
        if not existing:
            raise HTTPException(status_code=404, detail="Query not found")
        
        # Ensure IDs match
        if query_id != query.id:
            raise HTTPException(status_code=400, detail="Query ID mismatch")
        
        # Create VerifiedQuery object
        verified_query = VerifiedQuery(
            id=query.id,
            name=query.name,
            query_explanation=query.query_explanation,
            sql=query.sql,
            instructions=query.instructions,
            tables_used=query.tables_used,
            questions=[Question(text=q.text) for q in query.questions],
            follow_ups=query.follow_ups,
            verified_at=datetime.now(),
            verified_by=query.verified_by
        )
        
        # Save to database
        success = save_verified_query(verified_query, db)
        if not success:
            # Explicitly rollback if save failed
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update query")
        
        return {"status": "success", "id": query.id}
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Rollback on other exceptions
        db.rollback()
        logger.error(f"Error updating verified query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.delete("/api/verified_query/{query_id}", tags=["Verified Queries"])
async def api_delete_verified_query(
    query_id: str,
    db: Session = Depends(get_db_session)
):
    """API endpoint to delete a verified query"""
    try:
        # Check if query exists
        existing = get_verified_query(query_id, db)
        if not existing:
            raise HTTPException(status_code=404, detail="Query not found")
        
        # Delete the query
        success = delete_verified_query(query_id, db)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete query")
        
        return {"status": "success", "id": query_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting verified query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.post("/api/run_test_query", tags=["Query Execution"])
async def api_run_test_query(
    query: Dict[str, str] = Body(...),
    db: Session = Depends(get_db_session)
):
    """Run a test SQL query"""
    try:
        sql = query.get("sql")
        if not sql:
            raise HTTPException(status_code=400, detail="SQL query is required")
        
        # Use the same function that runs queries in the main app
        with Session(insurance_db_engine) as db:
            results = run_query(sql, db)
            return {
                "status": "success", 
                "results": results
            }
    except Exception as e:
        logger.error(f"Error running test query: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/api/verified_queries/options", tags=["Verified Queries"])
async def api_get_query_options(db: Session = Depends(get_db_session)):
    """API to get all queries as options for follow-ups"""
    queries = get_verified_queries(db)
    return [{"id": q.id, "name": q.name} for q in queries]

@app.get("/api/calendar_context")
async def api_get_calendar_context():
    """API endpoint to get calendar context"""
    try:
        context = get_calendar_context()
        return {"context": context}
    except Exception as e:
        logger.error(f"Error getting calendar context: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user_profile")
async def api_get_user_profile(db: Session = Depends(get_db_session)):
    """API endpoint to get user profile"""
    try:
        profile = get_user_profile(db)
        return profile
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user_profile")
async def api_update_user_profile(
    profile: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db_session)
):
    """API endpoint to update user profile"""
    try:
        user_id = int(profile.get("user_id", 1))
        name = profile.get("user_name", "")
        context = profile.get("user_context", "")
        
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        
        success = set_user_profile(user_id, name, context, db)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update profile")
        
        return {"status": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get_context")
async def api_get_context(db: Session = Depends(get_db_session)):
    """API endpoint to get context"""
    try:
        calendar_context = get_calendar_context()
        
        # Get user profile (requires DB session)
        if db:
            user_profile = get_user_profile(db)
        else:
            with Session(engine) as db:
                user_profile = get_user_profile(db)
        user_context = user_profile.get("user_context", "") 

        return {
            "calendar_context": calendar_context,
            "user_profile": user_context
        }
    except Exception as e:
        logger.error(f"Error fetching context: {str(e)}")
        return {
            "calendar_context": "",
            "user_profile": ""
        }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:

            data = await websocket.receive_json()
            action = data.get("action")
            question = data.get("question")
            session_id = data.get("session_id")

            logger.info(f"[{session_id}] Received action: {action} with question: {question}")

            iteration_count = 0
            MAX_REVIEW_ITERATIONS = 3 

            if action == "stop":
                await websocket.send_json({"status": "stopped"})
                continue

            # Fetch current context for each request
            with Session(engine) as db:
                context = await api_get_context(db)
                logger.info(f"Current context: {context}")

            if action == "get_intent_clarifications":
                logger.debug(f"Generating intent clarifications for: {question}")

                clarifications = generate_intent_clarifications(question, context, llm_service)
                
                await websocket.send_json({
                    "status": "ok",
                    "step": "intent_clarifications",
                    "clarifications": clarifications
                })


            elif action == "get_best_query":
                # Check if we should show intent clarifications first
                should_clarify = data.get("should_clarify", True)  # Default to True
                
                if should_clarify:
                    logger.debug(f"Offering intent clarifications for: {question}")
                    clarifications = generate_intent_clarifications(question, context, llm_service)
                    
                    # Only proceed to clarification step if we have multiple options
                    if len(clarifications) > 1:
                        await websocket.send_json({
                            "status": "ok",
                            "step": "intent_clarifications",
                            "clarifications": clarifications,
                            "original_question": question
                        })
                        continue  # Wait for user selection
                
                # If no clarification needed or user already selected a clarification
                logger.debug(f"Received question: {question}. Getting best query.")
                
                with Session(engine) as db:
                    best_query_result = get_best_query(question, llm_service, db=db)
                    print(f"Best query result: {best_query_result}")
                    verified_query = best_query_result["verified_query"]
                    
                    if not verified_query:
                        await websocket.send_json({"status": "no_match"})
                        continue
                    
                    # Send the best query to the client
                    await websocket.send_json({
                        "status": "ok",
                        "step": "best_query",
                        "verified_query": json.loads(verified_query.model_dump_json())
                    })

            # Add a new action to handle the selected clarification
            elif action == "select_clarification":
                selected_question = data.get("selected_question")
                logger.debug(f"User selected clarification: {selected_question}")
                
                # Update the question to the selected clarification
                question = selected_question
                
                # Proceed with best query selection using the clarified question
                with Session(engine) as db:
                    best_query_result = get_best_query(question, llm_service, db=db)
                    print(f"Best query result: {best_query_result}")
                    verified_query = best_query_result["verified_query"]
                    
                    if not verified_query:
                        await websocket.send_json({"status": "no_match"})
                        continue
                    
                    # Send the best query to the client
                    await websocket.send_json({
                        "status": "ok",
                        "step": "best_query",
                        "verified_query": json.loads(verified_query.model_dump_json())
                    })


            elif action == "get_recommendations":
                logger.debug(f"Getting recommendations for question: {question}")
                with Session(engine) as db:
                    verified_query_data = data.get("verified_query")
                    question = data.get("question")

                    # Option to enhance the question before recommendation ()
                    enhanced_question = question #enhance_question(question, context, llm_service)
                    logger.debug(f"Enhanced question: {enhanced_question}")

                    verified_query = VerifiedQuery(**verified_query_data)

                    # Get query change recommendations
                    recs = get_query_recommendations(verified_query, enhanced_question, context, llm_service)

                    # look for 'modifications_needed' in recs
                    if recs.get("modifications_needed") is None:
                        modifications = []
                    else:
                        modifications = recs["modifications"]

                    await websocket.send_json({
                        "status": "ok",
                        "step": "recommendations",
                        "enhanced_question": enhanced_question,
                        "modifications_needed": recs.get('modifications_needed', False),
                        "modifications": recs.get('modifications', 'No modifications needed'),
                        "explanation": recs.get('explanation', 'No explanation provided')
                    })


            elif action == "modify_query":
                logger.debug(f"Modifying query for question: {question}")
                sql = data.get("sql")
                modifications = data.get("modifications")
                iteration_count = data.get("iteration_count", 0)

                # Get questions
                original_question = data.get("original_question", question)
                enhanced_question = data.get("enhanced_question", question)

                # Generate modified SQL
                final_sql = modify_query(sql, modifications, llm_service)
                logger.debug(f"Modified SQL (iteration {iteration_count}): {final_sql}")
                
                #verified_query_data = data.get("verified_query")

                # Check if we need to review the SQL (only if not the final iteration)
                if iteration_count < MAX_REVIEW_ITERATIONS:
                    # Get verified query data
                    verified_query_data = data.get("verified_query")
                    verified_query = VerifiedQuery(**verified_query_data)
                    
                    # Send interim update to client
                    await websocket.send_json({
                        "status": "ok",
                        "step": "reviewing_sql",
                        "message": f"Reviewing SQL modifications (iteration {iteration_count + 1}/{MAX_REVIEW_ITERATIONS})...",
                        "iteration": iteration_count + 1,
                        "max_iterations": MAX_REVIEW_ITERATIONS
                    })
                    
                    # Review the modified SQL
                    review_results = review_modified_query(
                        original_sql=sql,
                        modified_sql=final_sql,
                        original_question=original_question,
                        enhanced_question=enhanced_question,
                        verified_query=verified_query,
                        llm_service=llm_service
                    )
                    
                    # If the SQL has issues and we haven't reached max iterations
                    if not review_results.get("is_valid", True) and iteration_count < MAX_REVIEW_ITERATIONS - 1:
                        # Send review results to client
                        await websocket.send_json({
                            "status": "ok",
                            "step": "sql_review_results",
                            "review_results": review_results,
                            "iteration": iteration_count + 1,
                            "max_iterations": MAX_REVIEW_ITERATIONS
                        })
                        
                        # If there's a corrected SQL, use it directly
                        if review_results.get("corrected_sql"):
                            final_sql = review_results["corrected_sql"]
                            
                            # Send the final SQL after corrections
                            await websocket.send_json({
                                "status": "ok",
                                "step": "modified_sql",
                                "final_sql": final_sql,
                                "is_valid": review_results.get("is_valid", True),
                                "review_message": review_results.get("explanation", "SQL review completed."),
                                "review_applied": review_results.get("corrected_sql") is not None
                            })
                        else:
                            # Otherwise, create new modifications based on review
                            new_modifications = [
                                {
                                    "type": "review_fix",
                                    "description": suggestion,
                                    "sql_impact": "Fix SQL issues"
                                }
                                for suggestion in review_results.get("suggestions", [])
                            ]
                            
                            # If we have valid new modifications, start another iteration
                            if new_modifications:
                                # Recursive call to the modify_query handler
                                await websocket.send_json({
                                    "status": "ok",
                                    "step": "additional_modifications",
                                    "sql": final_sql,
                                    "modifications": new_modifications,
                                    "iteration_count": iteration_count + 1,
                                    "verified_query": verified_query_data,
                                    "original_question": data.get("original_question", question),
                                    "enhanced_question": data.get("enhanced_question", question)
                                })
                                continue
                    else:
                        # SQL is valid or we reached max iterations, proceed with the current SQL
                        await websocket.send_json({
                            "status": "ok",
                            "step": "modified_sql",
                            "final_sql": final_sql,
                            "is_valid": review_results.get("is_valid", True),
                            "review_message": review_results.get("explanation", "SQL review completed.")
                        })
                else:
                    # We've reached max iterations, proceed with the current SQL
                    logger.warning(f"Max iterations reached for SQL modifications.")
                    await websocket.send_json({
                        "status": "ok",
                        "step": "modified_sql",
                        "final_sql": final_sql,
                        "max_iterations_reached": True
                    })


            elif action == "apply_additional_modifications":
                logger.debug(f"Applying additional modifications based on review")
                sql = data.get("sql")
                modifications = data.get("modifications")
                iteration_count = data.get("iteration_count", 0)
                
                # Call modify_query again with updated parameters
                final_sql = modify_query(sql, modifications, llm_service)
                
                # TODO: Similar to the code above - this could be refactored to avoid duplication
                # Send the modified SQL to the client
                await websocket.send_json({
                    "status": "ok",
                    "step": "modified_sql",
                    "final_sql": final_sql,
                    "iteration": iteration_count
                })


            elif action == "run_query":
                final_sql = data.get("sql")
                user_question = data.get("question")
                verified_query_data = data.get("verified_query")  # Get the verified query data if available
                query_explanation = None

                if verified_query_data:
                    verified_query = VerifiedQuery(**verified_query_data)
                    query_explanation = verified_query.query_explanation

                with Session(insurance_db_engine) as db:
                    try:
                        results = run_query(final_sql, db)

                        if not results or len(results.get('rows', [])) == 0:
                            await websocket.send_json({
                                "status": "ok",
                                "step": "narrative_generated",
                                "narrative": "No data was found for your query. Please try modifying your question or parameters.",
                            })
                            
                            # Then send an empty results structure to maintain the expected flow
                            await websocket.send_json({
                                "status": "ok", 
                                "step": "query_results",
                                "results": {"columns": [], "rows": []},
                                "chart_config": {"chart_applicable": False}
                            })            

                        else:

                            # First, generate the narrative
                            narrative = write_narrative(
                                question=user_question,
                                context=context,
                                data=results,
                                llm_service=llm_service
                            )

                            # Send interim update to client
                            await websocket.send_json({
                                "status": "ok",
                                "step": "narrative_generated",
                                "narrative": narrative,
                                "message": "Generating visualization..."
                            })

                            # Now generate chart configuration
                            chart_config = generate_chart_config(
                                results=results,
                                question=user_question,
                                narrative=narrative,
                                query_explanation=query_explanation,
                                llm_service=llm_service
                            )

                            # Send the complete results
                            await websocket.send_json({
                                "status": "ok",
                                "step": "query_results",
                                "results": results,
                                "narrative": narrative,
                                "chart_config": chart_config
                            })
                    except Exception as e:
                        await websocket.send_json({
                            "status": "error",
                            "step": "query_results",
                            "message": str(e)
                        })


            elif action == "get_follow_ups":
                query_id = data.get("query_id")
                logger.info(f"[{session_id}] Getting follow-ups for query_id: {query_id} ({data.get('query_name')})")
                with Session(engine) as db:
                    follow_ups = get_follow_up_queries(query_id, db)
                    logger.info(f"[{session_id}] Found {len(follow_ups)} follow-up recommendations.")

                    follow_ups_serialized = [fup.model_dump(mode="json") for fup in follow_ups]

                    await websocket.send_json({
                        "status": "ok",
                        "step": "follow_ups",
                        "follow_ups": follow_ups_serialized
                    })



    except WebSocketDisconnect:
        clients.remove(websocket)
    except Exception as e:
        # Full error and traceback to logs
        tb = traceback.format_exc()
        logger.error(f"Unhandled error:\n{tb}")

        # Clean message to client
        await websocket.send_json({
            "status": "error",
            "message": f"An internal error occurred. {str(e)}",
        })