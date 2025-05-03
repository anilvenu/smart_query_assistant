"""
Chart generator module for Smart Query Assistant.

This module generates chart configurations for visualizing query results.
"""

import logging
from typing import Dict, Any, Optional

from app.visualization.chart_analyzer import analyze_query_results

logger = logging.getLogger(__name__)

def generate_chart_config(
    results: Dict[str, Any], 
    question: str, 
    narrative: str,
    query_explanation: Optional[str] = None,
    llm_service=None
) -> Dict[str, Any]:
    """
    Generate chart configuration for visualizing query results.
    
    Args:
        results: Dictionary containing query results with columns and rows
        question: User question for context
        narrative: Generated narrative for the results
        query_explanation: The SQL query explanation if available
        llm_service: Optional LLM service for enhanced analysis
        
    Returns:
        Dictionary containing chart configuration
    """
    try:
        logger.info("Generating chart configuration...")
        
        # Analyze results to determine appropriate chart type
        chart_config = analyze_query_results(
            results, 
            question, 
            query_explanation, 
            llm_service
        )
        
        # Add reasoning from LLM to the chart config for transparency
        if "reasoning" in chart_config:
            chart_config["chart_generation_explanation"] = chart_config.pop("reasoning")
        
        return chart_config
    except Exception as e:
        logger.error(f"Error generating chart configuration: {str(e)}")
        return {
            "chart_type": "table",
            "chart_applicable": False,
            "error": str(e)
        }