import traceback
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Fast API
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import json

# For database connection
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.helper import (
    VerifiedQuery,
    enhance_question,
    generate_intent_clarifications,
    get_best_query,
    get_query_recommendations,
    get_follow_up_queries,
    modify_query
)

from app.agents.report_writer import (
    write_narrative
)

from app.gadgets.sql_runner import run_query

# Configurations
from app.utilities import config

# LLM service
from app.llm.llm_service import LLMService

# Configure database connections
engine = create_engine(config.APPLICATION_DB_CONNECTION_STRING)
insurance_db_engine = create_engine(config.BUSINESS_DB_CONNECTION_STRING)

# Initialize LLM service
llm_service = LLMService()


# Add some sample context
context = {
    "calendar_context": "Current date: 2025-04-30, Current year: 2025, Previous year: 2024, Current quarter: 2025 Q2, Previous quarter: 2025 Q1, Current month: 2025-04, Previous month: 2025-03",
    "user_profile": "Region: Northeast",
}

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

clients = set()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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

            if action == "stop":
                await websocket.send_json({"status": "stopped"})
                continue


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

                final_sql = modify_query(sql, modifications, llm_service)
                logger.debug(f"Final SQL: {final_sql}")

                # Send the modified SQL to the client
                await websocket.send_json({
                    "status": "ok",
                    "step": "modified_sql",
                    "final_sql": final_sql
                })

            elif action == "run_query":
                final_sql = data.get("sql")
                user_question = data.get("question")

                with Session(insurance_db_engine) as db:
                    try:
                        results = run_query(final_sql, db)

                        narrative = write_narrative(
                            question=user_question,
                            context=context,
                            data=results,
                            llm_service=llm_service
                        )

                        await websocket.send_json({
                            "status": "ok",
                            "step": "query_results",
                            "results": results,
                            "narrative": narrative
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