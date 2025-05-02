import json
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)


def build_report(question: str, context: Dict[str, Any], data: Dict[str, Any], llm_service) -> Dict[str, Any]:
    """
    Generate a report based on the question, context, and data.
    Uses a language model to create a human-readable
    explanation and SQL query.
    """

    narrative = write_narrative(question, context, data, llm_service)

    return {
        "narrative": "Test narrative", 
        "visualizations": []
        }


def write_narrative(question: str, context: Dict[str, Any], data: Dict[str, Any], llm_service) -> str:
    """
    Generate a narrative based on the question, context, and data.
    Uses a language model to create a human-readable explanation.
    """
    
    # Create a system prompt for the LLM
    system_prompt = """You are an expert in P&C Insurance data analysis and report writing.
    You are given a question, context, and data.
    Your task is to generate a human-readable narrative that explains the data in the context of the question."""

    # User prompt with question, data and context
    user_prompt = f"""
    Understand the question and the data provided, and answer the question in 1 - 2 sentences. 
    If there are any compelling insights you observed on the data that would be useful to the user, please provide in a separate paragraph of 1 - 2 sentences. 
    If there are no insights, don't mention anything about insights.

    Question: {question}
    
    Data: {json.dumps(data, indent=2)}

    Here is some additional context that you may use to answer the question.
    Context: {json.dumps(context, indent=2)}

    Avoid unnecessary preambles like "According to the data..." or "Based on the results...". Write with confident, declarative language. 
    Answer the question directly and concisely.
    """

    try:
        logger.info("Generating narrative with LLM...")
        
        # Get narrative from LLM
        narrative = llm_service.generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0
        )
        # Strip any leading/trailing whitespace
        narrative = narrative.strip()

    except Exception as e:
        print("Error generating narrative:", e)
        logger.error(f"Error generating narrative: {str(e)}")

    return narrative
