"""
Verified Query module for Smart Query Assistant.

Data classes and functions for working with verified queries,
including vector-based search and LLM-based recommendations.
"""
import json
import logging
from datetime import datetime
import calendar
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sentence_transformers import SentenceTransformer

from app.utilities import config
from app.models.verified_query import VerifiedQuery, Question

from app.utilities import prompt_builder

# Configure logging
logger = logging.getLogger(__name__)

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
    
    logger.debug(f"SQL Query: \n{sql}")
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

def get_calendar_context(db: Session) -> Dict[str, Any]:
    """
    Get calendar context for the current user.
    
    Args:
        db: Database session
    Returns:
        Dictionary with calendar context
    """
    # Example calendar context
    calendar_context = {
        "current_year": 2025,
        "current_quarter": 2,
        "previous_quarter": 1,
        "previous_year": 2024,
        "year_to_date": True
    }
    
    # In a real application, this would be fetched from the database or user profile
    return calendar_context



def enhance_question(question: str, context, llm_service) -> str:
    """
    Enhance a user question using LLM to make it more specific and clear.
    
    Args:
        question: User question
        llm_service: LLM service for generating enhanced question
    Returns:
        Enhanced question
    """

    # Create a system prompt for the LLM
    system_prompt = """You are an expert in P&C Insurance data analysis.
    Your task is to enhance user questions to make them more specific and clear."""

    # User prompt with the original question
    user_prompt = f"""
    You are helping clarify and enhance user questions for insurance data analysis. Your goal is to make them more specific and clear.

    Below is a user question the user wants answered using data. Use the rules below to enhance it.

    User Question:
    {question}

    Enhancement Rules:

    RULE #1: Use the calendar context below ONLY if the original question makes reference to it (e.g., "this year", "last 2 quarters", etc). DO NOT assume or add time period, unless clearly implied by the original question.
    Calendar Context: {context.get('calendar_context', 'None')}
    
    RULE #2: Use the user profile context below ONLY if the original question makes reference to it (e.g., "my region", "my agency", etc). DO NOT use user profile information unless clearly implied by the original question.
    User Profile: {context.get('user_profile', 'None')}

    RULE #3: If the question is general, keep it general. If no enhancement is needed, return the original question as is.
    
    RULE #4: Preserve the intent, structure, and tone of the original question.
    
    RULE #5: Return only the enhanced question with no extra commentary.

    If your response does not pass the above rules, please rephrase it to comply with the rules.

    Examples:
    - Input: "What is the total premium generated by each agency?" → Output: "What is the total premium generated by each agency?"
    - Input: "What is the total premium generated by each agency in my region this year?" (with Region: Northeast) → Output: "What is the total premium generated by each agency in the Northeast region during the current year (2025)?"
    """
    try:
        logger.info("Enhancing question with LLM...")
        
        # Get prompt from prompt builder
        system_prompt, user_prompt, verbose_flag = prompt_builder.build_prompt(
            prompt_id="enhance_question",
            params={
                "question": question,
                "context": context
            }
        )
        logger.error(f"Verbose: {verbose_flag}")
        if not system_prompt or not user_prompt:
            logger.error("Failed to build prompt for enhance_question")
            return question

        # Get enhanced question from LLM
        enhanced_question = llm_service.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0
        )
        # Strip any leading/trailing whitespace
        enhanced_question = enhanced_question.strip()
    except Exception as e:
        logger.error(f"Error generating enhanced question: {str(e)}")
        
    return enhanced_question


def generate_intent_clarifications(question: str, context: Dict[str, Any], llm_service) -> List[Dict[str, str]]:
    """
    Generate multiple intent clarifications for a user question.
    
    Args:
        question: Original user question
        context: Context dictionary with calendar and user information
        llm_service: LLM service for generating clarifications
        
    Returns:
        List of dictionaries with clarification options, each containing:
        - text: The clarified question text
        - explanation: Brief explanation of this interpretation
    """
    # Create a system prompt for the LLM
    system_prompt = """You are an expert in P&C Insurance data analysis.
    Your task is to generate clear variations of the user's question to ensure correct intent interpretation."""

    # User prompt for generating clarifications
    user_prompt = f"""
    Below is a user question related to insurance data analysis. Generate 3-4 different interpretations or clarifications
    of this question. These should represent slightly different ways to understand what the user might be asking.
    
    Original Question: "{question}"
    
    Use the context below only if directly relevant to resolving ambiguities:
    Calendar Context: {context.get('calendar_context', 'None')}
    User Profile: {context.get('user_profile', 'None')}
    
    Rules:
    1. Each variation should be a plausible interpretation of the original intent
    2. Include the original question as one of the options
    3. Variations might differ in:
       - Time periods referenced (current quarter, year-to-date, previous quarter, etc.) or no time period
       - Categorical value filters applied based on User Profile (specific items, all items, omitting the filter altogether, etc.)
       - Metric focus (totals, counts, averages, etc.)
       - Grouping/filtering level 
    4. Each variation should be a complete, well-formed question
    5. Don't make interpretations that completely change the user's intent
    
    Return a JSON array with each item containing:
    - "text": the clarified question text
    - "explanation": a brief, one-sentence explanation of this interpretation
    
    The first option should always be the original question with an explanation.
    """
    
    try:
        logger.info("Generating intent clarifications with LLM...")
        
        # Get clarifications from LLM as structured output
        clarifications = llm_service.generate_structured_output(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2
        )
        
        # Ensure we have a list of clarifications
        if isinstance(clarifications, dict) and "clarifications" in clarifications:
            return clarifications["clarifications"]
        elif isinstance(clarifications, list):
            return clarifications
        else:
            # Fallback: return just the original question
            return [{"text": question, "explanation": "Original question without modification."}]
            
    except Exception as e:
        logger.error(f"Error generating intent clarifications: {str(e)}")
        # Fallback: return just the original question
        return [{"text": question, "explanation": "Original question without modification."}]



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

    Tailoring documentation for the SQL:
    {verified_query.instructions}

    User question that the SQL must me tailored to answer: {question}
    
    Based on the SQL and the user's question, provide specific recommendations for tailoring the SQL query.
    Follow the tailoring documentation and identify exactly what changes need to be made.

    Rules for writing recommendations:
    - DO NOT assume table names or columns that are not in the SQL or in the documentation.
    - DO NOT recommend joining additional tables unless explicitly mentioned in the SQL or documentation.
    - DO NOT recommend adding new columns unless explicitly mentioned in the SQL or documentation.
    - DO NOT add predicates with placeholders unresolved.

    Return a JSON with these fields:
    - "modifications_needed": boolean indicating if modifications are needed
    - "modifications": list of specific modifications to make, with each item containing:
    - "type": modification type (e.g., "filter", "column", "grouping", "sorting")
    - "description": detailed description of the change
    - "sql_impact": how it affects the SQL query
    - "explanation": explanation of why these modifications are recommended
    """
    
#    User's question may contain temporal and user profile or property references. Resolve them using the context below:
#    Calendar Information: {context.get('calendar_context', 'None')}
#    User Information: {context.get('user_profile', 'None')}
    



    logger.info(f"User prompt for LLM: {user_prompt}")
    logger.info(f"System prompt for LLM: {system_prompt}")

    # Get response from LLM
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
        logger.error(f"Error generating modified SQL: {str(e)}")

    return modified_sql


def review_modified_query(
    original_sql: str, 
    modified_sql: str, 
    original_question: str, 
    enhanced_question: str, 
    verified_query: VerifiedQuery, 
    llm_service
) -> Dict[str, Any]:
    """
    Review a modified SQL query for correctness, alignment with user intent,
    and potential issues like hallucinated column/table names.
    
    Args:
        original_sql: The original verified SQL query
        modified_sql: The modified SQL query to review
        original_question: The original user question
        enhanced_question: The enhanced/clarified question
        verified_query: The VerifiedQuery object with metadata
        llm_service: LLM service for reviewing
        
    Returns:
        Dictionary with review results including:
        - is_valid: Boolean indicating if the query is valid
        - issues: List of identified issues
        - suggestions: List of suggested improvements
        - explanation: Explanation of review findings
    """
    # Create a system prompt for the LLM
    system_prompt = f"""You are an expert SQL reviewer for {config.BUSINESS_DATABASE_TYPE}. 
    Your task is to analyze a modified SQL query for correctness and alignment with user intent."""
    
    # User prompt for reviewing the modified SQL
    user_prompt = f"""
    Please review this modified SQL query for correctness, SQL syntax, and alignment with the user's question.
    
    Original SQL Query:
    ```sql
    {original_sql}
    ```
    
    Modified SQL Query:
    ```sql
    {modified_sql}
    ```
    
    Original User Question: {original_question}
    
    Enhanced User Question: {enhanced_question}
    
    SQL Query Explanation:
    {verified_query.query_explanation}
    
    SQL Modification Instructions:
    {verified_query.instructions}
    
    Tables Used: {', '.join(verified_query.tables_used)}
    
    Please analyze the modified SQL query and identify any:
    1. SQL syntax errors or logical errors
    2. Hallucinated table or column names not mentioned in the original SQL or modification instructions
    3. Misalignment with the user's question intent
    4. Poor SQL practices or performance issues
    5. Missing filters, grouping, or sorting needed to properly answer the question
    
    Return a JSON with these fields:
    - "is_valid": boolean indicating if the query is valid and ready to run
    - "issues": array of identified issues (empty if none found)
    - "suggestions": array of suggested improvements (empty if none needed)
    - "explanation": string with brief explanation of your findings
    - "corrected_sql": string with corrected SQL only if improvements are needed (otherwise null)
    """
    
    try:
        logger.info("Reviewing modified SQL with LLM...")
        
        # Get review results from LLM
        review_results = llm_service.generate_structured_output(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1
        )
        
        return review_results
    except Exception as e:
        logger.error(f"Error reviewing modified SQL: {str(e)}")
        # Return a default response indicating review failure
        return {
            "is_valid": False,
            "issues": ["Failed to complete SQL review due to an error."],
            "suggestions": ["Please check the SQL manually for any issues."],
            "explanation": f"Review process encountered an error: {str(e)}",
            "corrected_sql": None
        }


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
            # Generate embedding
            embedding_vector = embedding_model.encode(question.text)
            vector_str = '[' + ','.join(str(x) for x in embedding_vector) + ']'
            
            db.execute(text("""
            INSERT INTO question (question_text, verified_query_id, vector_embedding)
            VALUES (:text, :vq_id, CAST(:embedding AS vector))
            """), {
                "text": question.text,
                "vq_id": verified_query.id,
                "embedding": vector_str
            })
        
        logger.info(f"Inserted {len(verified_query.questions)} questions for query ID: {verified_query.id}")
        logger.info(f"Deleted existing questions and follow-ups for query ID: {verified_query.id}")
        
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
        
        logger.info(f"Inserted {len(verified_query.follow_ups)} follow-ups for query ID: {verified_query.id}")
        
        # Explicitly commit the transaction
        db.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving verified query: {str(e)}")
        db.rollback()
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
        
        # Commit changes
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error deleting verified query: {str(e)}")
        db.rollback()
        return False


#---------------------------------------------------------------------------
# User Profile and Calendar Context Functions
#---------------------------------------------------------------------------

def get_calendar_context() -> str:
    """
    Generate calendar context string based on current date.
    
    Returns:
        Calendar context string
    """
    now = datetime.now()
    
    # Current date
    current_date = now.strftime('%Y-%m-%d')
    
    # Current year and previous year
    current_year = now.year
    previous_year = current_year - 1
    
    # Current quarter and previous quarter
    current_month = now.month
    current_quarter = (current_month - 1) // 3 + 1
    previous_quarter_month = current_month - 3
    previous_quarter_year = current_year
    
    if previous_quarter_month <= 0:
        previous_quarter_month += 12
        previous_quarter_year -= 1
    
    previous_quarter = (previous_quarter_month - 1) // 3 + 1
    
    # Current month and previous month
    current_month_str = now.strftime('%Y-%m')
    
    previous_month = current_month - 1
    previous_month_year = current_year
    
    if previous_month <= 0:
        previous_month += 12
        previous_month_year -= 1
    
    previous_month_str = f"{previous_month_year}-{previous_month:02d}"
    
    # Build the context string
    context = (
        f"Current date: {current_date}, "
        f"Current year: {current_year}, "
        f"Previous year: {previous_year}, "
        f"Current quarter: {current_year} Q{current_quarter}, "
        f"Previous quarter: {previous_quarter_year} Q{previous_quarter}, "
        f"Current month: {current_month_str}, "
        f"Previous month: {previous_month_str}"
    )
    
    return context

def get_user_profile(db: Session) -> Dict[str, str]:
    """
    Get the user profile information.
    
    Args:
        db: Database session
        
    Returns:
        User profile information
    """
    try:
        # For simplicity, we'll assume there's a single user (id=1)
        result = db.execute(
            text("SELECT id, name, profile_context FROM users WHERE id = 1")
        ).fetchone()
        
        if result:
            return {
                "user_id": result[0],
                "user_name": result[1],
                "user_context": result[2] or ""
            }
        else:
            # Create default user if not found
            db.execute(
                text("INSERT INTO users (id, name, profile_context) VALUES (1, 'Default User', 'Region: Northeast')")
            )
            db.commit()
            
            return {
                "user_id": 1,
                "user_name": "Default User",
                "user_context": "Region: Northeast"
            }
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        # Return default values on error
        return {
            "user_id": 1,
            "user_name": "Default User",
            "user_context": "Region: Northeast"
        }

def set_user_profile(user_id: int, name: str, context: str, db: Session) -> bool:
    """
    Update the user profile information.
    
    Args:
        user_id: User ID
        name: User name
        context: User profile context
        db: Database session
        
    Returns:
        Success status
    """
    try:
        # Update user profile
        db.execute(
            text("UPDATE users SET name = :name, profile_context = :context WHERE id = :id"),
            {"id": user_id, "name": name, "context": context}
        )
        db.commit()
        
        return True
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        db.rollback()
        return False