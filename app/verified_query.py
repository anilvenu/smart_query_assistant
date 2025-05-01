"""
Verified Query module for Smart Query Assistant.

Data classes and functions for working with verified queries,
including vector-based search and LLM-based recommendations.
"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from app import config
from sentence_transformers import SentenceTransformer

# Configure logging
logger = logging.getLogger(__name__)

# Data Classes
class Question(BaseModel):
    """Data class for a question with its vector embedding."""
    text: str
    vector_embedding: Optional[bytes] = None
    
    class Config:
        from_attributes = True

class VerifiedQuery(BaseModel):
    """Data class for verified SQL queries including questions and follow-ups."""
    id: str
    name: str
    query_explanation: str
    sql: str
    instructions: Optional[str] = None
    tables_used: List[str] = []
    questions: List[Question] = []
    follow_ups: List[str] = []
    verified_at: datetime
    verified_by: str

    class Config:
        from_attributes = True

# Initialize the sentence transformer model for embeddings
embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)

# Database connection
engine = create_engine(config.APPLICATION_DB_CONNECTION_STRING, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Get a database session
def get_db_session():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------------------------------------------------------
# Database setup and utility functions for verified queries
# -------------------------------------------------------------------------------
def get_verified_query(query_id: str, db: Session, include_embeddings=False) -> Optional[VerifiedQuery]:
    """
    Get a verified query by ID including its questions and follow-ups.
    
    Args:
        query_id: Query ID
        db: Database session
        
    Returns:
        VerifiedQuery object or None if not found
    """
    # Get the basic query data
    result = db.execute(
        text("SELECT * FROM verified_query WHERE id = :id"),
        {"id": query_id}
    )
    
    # Get column names first
    columns = result.keys()
    
    # Now fetch the row
    query = result.fetchone()
    
    if not query:
        return None
    
    # Convert row to dict using the columns we got earlier
    query_dict = dict(zip(columns, query))
    
    # Convert tables_used to a list if it's not already
    if query_dict.get("tables_used") is None:
        query_dict["tables_used"] = []
    
    # Get questions for this query
    questions_result = db.execute(
        text("SELECT question_text, vector_embedding FROM question WHERE verified_query_id = :id"),
        {"id": query_id}
    )
    
    questions = []
    for q_row in questions_result:
        questions.append(Question(
            text=q_row[0],
            vector_embedding=q_row[1] if include_embeddings else None
        ))
    
    # Get follow-ups for this query
    followups_result = db.execute(
        text("SELECT target_query_id FROM follow_up WHERE source_query_id = :id"),
        {"id": query_id}
    )
    
    follow_ups = [row[0] for row in followups_result]
    
    # Create complete VerifiedQuery
    return VerifiedQuery(
        id=query_dict["id"],
        name=query_dict["name"],
        query_explanation=query_dict["query_explanation"],
        sql=query_dict["sql"],
        instructions=query_dict.get("instructions"),
        tables_used=query_dict["tables_used"],
        questions=questions,
        follow_ups=follow_ups,
        verified_at=query_dict["verified_at"],
        verified_by=query_dict["verified_by"]
    )

def get_verified_queries(db: Session, include_embeddings=False) -> List[VerifiedQuery]:
    """
    Get all verified queries from the database as well as follow ups and questions.
    
    Args:
        db: Database session
        
    Returns:
        List of VerifiedQuery objects
    """
    result = db.execute(text("SELECT id FROM verified_query"))
    
    verified_queries = []
    for row in result:
        query_id = row[0]
        vq = get_verified_query(query_id, db, include_embeddings)
        if vq:
            verified_queries.append(vq)
    
    return verified_queries


def get_verified_queries_by_vector_search(question: str, n: int = 5, db: Session = None) -> List[Dict[str, Any]]:
    """
    Get verified queries using vector search based on question similarity.
    
    Args:
        question: User question
        n: Maximum number of results to return
        db: Database session
        
    Returns:
        List of verified queries with similarity scores
    """
    if db is None:
        db = next(get_db_session())
    
    # Generate embedding for the question
    embedding = embedding_model.encode(question)
    
    # Convert the embedding to a string representation that PostgreSQL can understand
    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
    
    # Use raw SQL with proper vector syntax for PostgreSQL
    # We're avoiding parameter binding for the vector part since that's causing the issue
    sql = f"""
    SELECT 
        vq.id, 
        1 - (q.vector_embedding <=> '{embedding_str}'::vector) AS similarity,
        q.question_text
    FROM 
        question q
        JOIN verified_query vq ON q.verified_query_id = vq.id
    ORDER BY 
        similarity DESC
    LIMIT :n
    """
    
    print(sql)
    # Execute the query with only the non-vector parameter
    results = db.execute(text(sql), {"n": n}).fetchall()
    
    # Get unique query IDs with their best similarity score
    query_similarities = {}
    question_matches = {}
    
    for row in results:
        query_id = row[0]
        similarity = float(row[1])
        question_text = row[2]
        
        # Keep the highest similarity score for each query
        if query_id not in query_similarities or similarity > query_similarities[query_id]:
            query_similarities[query_id] = similarity
            question_matches[query_id] = question_text
    
    # Get the full verified queries
    verified_queries = []
    for query_id, similarity in query_similarities.items():
        vq = get_verified_query(query_id, db)
        if vq:
            verified_queries.append({
                "verified_query": vq,
                "similarity": similarity,
                "matched_question": question_matches[query_id]
            })
    
    # Sort by similarity
    verified_queries.sort(key=lambda x: x["similarity"], reverse=True)
    
    return verified_queries

def get_best_query(question: str, llm_service, db: Session = None) -> Optional[Dict[str, Any]]:
    """
    Get the best verified query for a question using LLM-based selection.
    
    Args:
        question: User question
        llm_service: LLM service for matching queries
        db: Database session
        
    Returns:
        Dictionary with verified query and similarity or None if no match
    """
    if db is None:
        db = next(get_db_session())
    
    # First, get candidate queries using vector search
    candidates = get_verified_queries_by_vector_search(question, n=5, db=db)
    
    if not candidates:
        return None
    
    # If only one candidate, return it
    if len(candidates) == 1:
        return candidates[0]
    
    # Create a prompt for the LLM to select the best query
    system_prompt = """You are an expert at matching user questions with verified SQL queries.
Your task is to analyze the user's question and select the most appropriate verified query from candidates."""
    
    # Create a structured representation of candidate queries
    candidates_str = ""
    for i, candidate in enumerate(candidates):
        vq = candidate["verified_query"]
        candidates_str += f"Candidate {i+1}:\n"
        candidates_str += f"Name: {vq.name}\n"
        candidates_str += f"Explanation: {vq.query_explanation}\n"
        candidates_str += f"Matched Question: {candidate['matched_question']}\n"
    
    user_prompt = f"""User Question: {question}

Candidate verified queries along with their explanations and question answered by the query:
{candidates_str}

Based on the user's question, select the most appropriate verified query.
Analyze the semantic meaning of the question, not just keyword matching.
Return a JSON with these fields:
- "best_match_index": integer with the index of the best matching candidate (1-based)
- "confidence": float between 0 and 1 indicating your confidence in the match
- "reasoning": string explaining why this is the best match
"""
    
    # Get response from LLM
    response = llm_service.generate_structured_output(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.1
    )
    
    # Get the best match index (1-based in the response)
    best_index = response.get("best_match_index", 1) - 1
    
    # Ensure the index is valid
    if not 0 <= best_index < len(candidates):
        best_index = 0
    
    # Add confidence and reasoning to the result
    best_match = candidates[best_index]
    best_match["confidence"] = response.get("confidence", 0.0)
    best_match["reasoning"] = response.get("reasoning", "")
    
    return best_match

def get_query_recommendations(verified_query: VerifiedQuery, question: str, context: Dict[str, Any], llm_service) -> Dict[str, Any]:
    """
    Get recommendations for tailoring a verified query to meet user needs.
    
    Args:
        verified_query: Verified query to tailor
        context: Context dictionary with user question and other context
        llm_service: LLM service for generating recommendations
        
    Returns:
        Dictionary with recommendations
    """
    print("Getting recommendations for tailoring the query")
    if not verified_query:
        raise ValueError("Verified query is required")
    if not question:
        raise ValueError("User question is required")


    system_prompt = f"""You are an expert SQL developer for {config.BUSINESS_DATABASE_TYPE}. 
    Your task is to analyze a verified SQL query and provide recommendations for tailoring it to the user's specific needs."""

    # Get the question texts for context
    question_texts = [q.text for q in verified_query.questions]

    # Create a prompt with query details and context
    user_prompt = f"""SQL:
    {verified_query.sql}

    Explanation:
    {verified_query.query_explanation}

    This SQL query is designed to answer the following questions:
    {json.dumps(question_texts, indent=2)}

    Tailoring instructions for the SQL:
    {verified_query.instructions}

    User question that the SQL must me tailored to answer: {question}

    Calendar Information: {context.get('calendar_context', 'None')}

    User Information: {context.get('user_profile', 'None')}

    Other Context: {context.get('session_context', 'None')}

    Based on the SQL and the user's question, provide specific recommendations for tailoring the SQL query.
    Follow the tailoring instructions and identify exactly what changes need to be made.
    Do not make up table names or columns that are not in the SQL or in the instructions.
    Do not add predicates with placeholders unresolved.

    Return a JSON with these fields:
    - "modifications_needed": boolean indicating if modifications are needed
    - "modifications": list of specific modifications to make, with each item containing:
    - "type": modification type (e.g., "filter", "column", "grouping", "sorting")
    - "description": detailed description of the change
    - "sql_impact": how it affects the SQL query
    - "explanation": explanation of why these modifications are recommended
    """
    
    logger.debug(f"User prompt for LLM: {user_prompt}")
    logger.debug(f"System prompt for LLM: {system_prompt}")
    # Get response from LLM
    print('-------------->>>>>>>>>>>> Getting recommendations')
    response = llm_service.generate_structured_output(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.1
    )
    
    return response


def modify_query(sql: str, modifications: List[Dict[str, Any]], llm_service) -> str:
    """
    Modify a SQL query based on the provided modifications.
    
    Args:
        sql: Original SQL query
        modifications: List of modifications to apply
    Returns:
        Modified SQL query
    """
    # If no modifications are needed, return the original SQL
    if not modifications:
        return sql

    # Create a system prompt for the LLM
    system_prompt = """You are an expert SQL developer for PostgreSQL. 
                       Your task is to analyze and modify SQL based on specific requirements. 
                       Your response will be a valid SQL query."""

    # User prompt with original SQL and modifications
    user_prompt = f"""Original SQL:
            {sql}

            Modification instructions:
            {modifications}

            Column Alias Guidelines:
            - Change only if necessary
            - Match the verb from user's question
            - Keep prefixes if present
            - Maintain quote style and capitalization

            Return only the modified SQL query. Do NOT include any other text or explanations.
            """

    try:
        logger.info("Adjusting SQL query")
        
        # Get modified SQL from LLM
        modified_sql = llm_service.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0
        )
        # Strip any leading/trailing whitespace
        modified_sql = modified_sql.strip()

    except Exception as e:
        print("Error generating modified SQL:", e)
        logger.error(f"Error generating modified SQL: {str(e)}")

    return modified_sql


def get_follow_up_queries(query_id: str, db: Session) -> List[VerifiedQuery]:
    """
    Get follow-up verified queries for a query ID.
    
    Args:
        query_id: Query ID
        db: Database session
        
    Returns:
        List of follow-up verified queries
    """
    # Get the source verified query first
    source_query = get_verified_query(query_id, db)
    
    if not source_query or not source_query.follow_ups:
        return []
    
    # Get all follow-up queries
    follow_up_queries = []
    for follow_up_id in source_query.follow_ups:
        follow_up_query = get_verified_query(follow_up_id, db)
        if follow_up_query:
            follow_up_queries.append(follow_up_query)
    
    return follow_up_queries

def save_verified_query(verified_query: VerifiedQuery, db: Session) -> bool:
    """
    Save a verified query to the database.
    
    Args:
        verified_query: VerifiedQuery object to save
        db: Database session
        
    Returns:
        Success status
    """
    try:
        # Begin transaction
        transaction = db.begin()
        
        # Insert or update the verified query
        query = """
        INSERT INTO verified_query (
            id, name, query_explanation, sql, instructions, 
            tables_used, verified_at, verified_by
        ) VALUES (
            :id, :name, :query_explanation, :sql, :instructions, 
            :tables_used, :verified_at, :verified_by
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            query_explanation = EXCLUDED.query_explanation,
            sql = EXCLUDED.sql,
            instructions = EXCLUDED.instructions,
            tables_used = EXCLUDED.tables_used,
            verified_at = EXCLUDED.verified_at,
            verified_by = EXCLUDED.verified_by
        """
        
        db.execute(text(query), {
            "id": verified_query.id,
            "name": verified_query.name,
            "query_explanation": verified_query.query_explanation,
            "sql": verified_query.sql,
            "instructions": verified_query.instructions,
            "tables_used": verified_query.tables_used,
            "verified_at": verified_query.verified_at,
            "verified_by": verified_query.verified_by
        })
        
        # Delete existing questions for this query
        db.execute(
            text("DELETE FROM question WHERE verified_query_id = :id"),
            {"id": verified_query.id}
        )
        
        # Insert questions with vector embeddings
        for question in verified_query.questions:
            # Generate embedding if not provided
            embedding = question.vector_embedding
            if embedding is None:
                embedding_vector = embedding_model.encode(question.text)
                embedding = embedding_vector.tobytes()
            
            db.execute(text("""
            INSERT INTO question (question_text, verified_query_id, vector_embedding)
            VALUES (:text, :vq_id, :embedding)
            """), {
                "text": question.text,
                "vq_id": verified_query.id,
                "embedding": embedding
            })
        
        # Delete existing follow-ups for this query
        db.execute(
            text("DELETE FROM follow_up WHERE source_query_id = :id"),
            {"id": verified_query.id}
        )
        
        # Insert follow-ups
        for follow_up_id in verified_query.follow_ups:
            db.execute(text("""
            INSERT INTO follow_up (source_query_id, target_query_id)
            VALUES (:source_id, :target_id)
            """), {
                "source_id": verified_query.id,
                "target_id": follow_up_id
            })
        
        # Commit transaction
        transaction.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error saving verified query: {str(e)}")
        if transaction:
            transaction.rollback()
        return False

def delete_verified_query(query_id: str, db: Session) -> bool:
    """
    Delete a verified query from the database.
    
    Args:
        query_id: Query ID to delete
        db: Database session
        
    Returns:
        Success status
    """
    try:
        # Begin transaction
        transaction = db.begin()
        
        # Delete questions for this query
        db.execute(
            text("DELETE FROM question WHERE verified_query_id = :id"),
            {"id": query_id}
        )
        # Delete follow-ups for this query
        db.execute(
            text("DELETE FROM follow_up WHERE source_query_id = :id"),
            {"id": query_id}
        )

        # Delete the verified query
        db.execute(
            text("DELETE FROM verified_query WHERE id = :id"),
            {"id": query_id}
        )
        
        # Commit transaction
        transaction.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error deleting verified query: {str(e)}")
        if transaction:
            transaction.rollback()
        return False