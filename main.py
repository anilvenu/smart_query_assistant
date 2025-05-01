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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.verified_query import (
    VerifiedQuery,
    Question,
    get_verified_query,
    get_verified_queries_by_vector_search,
    get_best_query,
    get_query_recommendations,
    get_follow_up_queries,
    modify_query
)
from app.sql_runner import run_query

# Configurations
from app import config

# LLM service
from app.llm_service import LLMService

# Configure database connections
engine = create_engine(config.APPLICATION_DB_CONNECTION_STRING)
insurance_db_engine = create_engine(config.BUSINESS_DB_CONNECTION_STRING)

# Initialize LLM service
llm_service = LLMService()


# Add some sample context
context = {
    "calendar_context": "Current quarter: 2025 Q2, Previous quarter: 2025 Q1",
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

            if action == "get_best_query":
                print(f"Received question: {question}. Getting best query.")

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
                print(f"Getting recommendations for question: {question}")
                with Session(engine) as db:
                    verified_query_data = data.get("verified_query")
                    question = data.get("question")

                    verified_query = VerifiedQuery(**verified_query_data)

                    recs = get_query_recommendations(verified_query, question, context, llm_service)

                    print(f"Recommendations: {recs}")
                    # look for 'modifications_needed' in recs
                    if recs.get("modifications_needed") is None:
                        modifications = []
                    else:
                        modifications = recs["modifications"]

                    await websocket.send_json({
                        "status": "ok",
                        "step": "recommendations",
                        "modifications_needed": recs.get('modifications_needed', False),
                        "modifications": recs.get('modifications', 'No modifications needed'),
                        "explanation": recs.get('explanation', 'No explanation provided')
                    })

            elif action == "modify_query":

                print(f"Modifying query for question: {question}")
                sql = data.get("sql")
                modifications = data.get("modifications")
                print(f"Modifications: {modifications}")
                print(f"SQL: {sql}")
                final_sql = modify_query(sql, modifications, llm_service)
                print(f"Final SQL: {final_sql}")

                await websocket.send_json({
                    "status": "ok",
                    "step": "modified_sql",
                    "final_sql": final_sql
                })

            elif action == "run_query":
                final_sql = data.get("sql")
                with Session(insurance_db_engine) as db:
                    try:
                        results = run_query(final_sql, db)
                        await websocket.send_json({
                            "status": "ok",
                            "step": "query_results",
                            "results": results
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