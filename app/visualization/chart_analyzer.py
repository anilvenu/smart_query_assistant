"""
Chart analyzer module for Smart Query Assistant.

This module analyzes query results and determines appropriate chart types
and configurations based on the data structure.
"""

import logging
import traceback
import json
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Define chart type constants
CHART_TYPE_BAR = "bar"
CHART_TYPE_LINE = "line"
CHART_TYPE_PIE = "pie"
CHART_TYPE_COLUMN = "column"  # Vertical bar chart
CHART_TYPE_TABLE = "table"

# Define color palettes based on the provided specifications
COLOR_PALETTE = {
    "blues": ["#E8F0E9", "#C5D5E5", "#A9B9D1", "#8BA2BD", "#779CCD", "#5582B0", "#3E6044"],
    "ambers": ["#F9F0DA", "#F5E7C0", "#F0DEA0", "#E3B447", "#C99A35", "#A97B23", "#816014"],
    "reds": ["#F4DEDE", "#EABFBF", "#E0A0A0", "#ED7D31", "#C25F4E", "#9E4139", "#6C2525"],
    "greens": ["#E8F0E9", "#D0DFD5", "#B8CFC1", "#8AB391", "#698E6D", "#48584B", "#412C3C"],
    "default": ["#8AB391", "#779CCD", "#E3B447", "#ED7D31"]  # One from each group for default palette
}

def analyze_query_results(results: Dict[str, Any], question: str, query_explanation: Optional[str] = None, llm_service=None) -> Dict[str, Any]:
    """
    Analyze query results and determine appropriate chart types and configurations.
    
    Args:
        results: Dictionary containing query results with columns and rows
        question: User question for context
        query_explanation: The SQL query explanation if available
        llm_service: Optional LLM service for enhanced analysis
        
    Returns:
        Dictionary containing chart configuration
    """
    if not results or not results.get("rows") or not results.get("columns"):
        return {"chart_type": CHART_TYPE_TABLE, "chart_applicable": False}
    
    # Get columns and data
    columns = results["columns"]
    rows = results["rows"]
    
    if len(rows) == 0:
        return {"chart_type": CHART_TYPE_TABLE, "chart_applicable": False}
    
    # Perform basic analysis of data types
    column_types = _analyze_column_types(columns, rows)
    
    # If LLM service is available, use it for enhanced chart analysis
    if llm_service:
        llm_chart_config = _determine_chart_type_with_llm(
            columns, column_types, rows, question, query_explanation, llm_service
        )
        
        if llm_chart_config:
            # Merge with basic chart configuration
            chart_config = _build_chart_config(
                llm_chart_config["chart_type"], 
                llm_chart_config["chart_columns"], 
                columns, rows, question
            )
            return chart_config
    
    # Fall back to rule-based approach if LLM is not available or fails
    chart_type, chart_columns = _determine_chart_type(columns, column_types, rows, question)
    chart_config = _build_chart_config(chart_type, chart_columns, columns, rows, question)
    
    return chart_config

def _determine_chart_type_with_llm(
    columns: List[str], 
    column_types: Dict[str, str], 
    rows: List[Dict[str, Any]], 
    question: str,
    query_explanation: Optional[str],
    llm_service
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to determine the most appropriate chart type based on data and question context.
    
    Args:
        columns: List of column names
        column_types: Dictionary of column data types
        rows: List of data rows
        question: User question for context
        query_explanation: The SQL query explanation if available
        llm_service: LLM service for enhanced analysis
        
    Returns:
        Dictionary with chart type and column mappings
    """
    try:
        # Prepare data sample for LLM
        sample_rows = rows[:5] if len(rows) > 5 else rows
        sample_data = json.dumps(sample_rows, indent=2)
        
        # Create a system prompt for the LLM
        system_prompt = """You are an expert data visualization specialist. 
        Your task is to analyze data and determine the most appropriate chart type for visualization."""
        
        # User prompt with data context
        user_prompt = f"""
        I need to create a data visualization for a query result. Please analyze the following information 
        and recommend the best chart type and configuration.
        
        User Question: "{question}"
        
        {f'Query Explanation: "{query_explanation}"' if query_explanation else ''}
        
        Data Columns (with types):
        {json.dumps({col: col_type for col, col_type in column_types.items()}, indent=2)}
        
        Sample Data (first few rows):
        {sample_data}
        
        Total number of rows: {len(rows)}
        
        Analyze the data and question to determine:
        1. Which chart type would best represent this data (bar, column, line, pie, or table)
        2. Which columns should be used for:
           - x-axis (categories/time)
           - y-axis (measures/values)
           - series grouping (if applicable)
           - labels (for pie charts)
        3. Whether multiple series are needed
        4. Any special considerations for this visualization
        
        Rules:
        - Only recommend chart types from this list: bar (horizontal), column (vertical), line, pie, or table
        - For pie charts, ensure the data has a clear categorical field and one numeric field, with a reasonable number of categories
        - For line charts, ensure there is a logical progression in the data (like time)
        - If no good visualization is possible, recommend "table"
        
        Return your answer as a JSON object with these fields:
        - "chart_type": The recommended chart type (bar, column, line, pie, or table)
        - "chart_columns": An object with arrays for x_axis, y_axis, series, and labels
        - "reasoning": A brief explanation of your recommendation
        """
        
        # Get chart recommendation from LLM
        chart_recommendation = llm_service.generate_structured_output(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2
        )
        
        # Extract and validate chart configuration
        if not chart_recommendation or "chart_type" not in chart_recommendation:
            logger.warning("LLM did not return valid chart recommendation")
            return None
        
        # Ensure chart_type is valid
        chart_type = chart_recommendation.get("chart_type", "").lower()
        if chart_type not in [CHART_TYPE_BAR, CHART_TYPE_COLUMN, CHART_TYPE_LINE, CHART_TYPE_PIE, CHART_TYPE_TABLE]:
            logger.warning(f"Invalid chart type from LLM: {chart_type}")
            return None
        
        # Get chart columns from recommendation
        chart_columns = chart_recommendation.get("chart_columns", {})
        
        # Validate chart columns
        valid_columns = {
            "x_axis": [col for col in chart_columns.get("x_axis", []) if col in columns],
            "y_axis": [col for col in chart_columns.get("y_axis", []) if col in columns],
            "series": [col for col in chart_columns.get("series", []) if col in columns],
            "labels": [col for col in chart_columns.get("labels", []) if col in columns]
        }
        
        # Log the chart selection reasoning
        logger.info(f"LLM chart selection reasoning: {chart_recommendation.get('reasoning', 'No reasoning provided')}")
        
        return {
            "chart_type": chart_type,
            "chart_columns": valid_columns,
            "reasoning": chart_recommendation.get("reasoning", "")
        }
        
    except Exception as e:
        logger.error(f"Error determining chart type with LLM: {str(e)}")
        return None

def _determine_chart_type(
    columns: List[str], 
    column_types: Dict[str, str], 
    rows: List[Dict[str, Any]], 
    question: str
) -> Tuple[str, Dict[str, List[str]]]:
    """
    Determine the most appropriate chart type based on data structure.
    
    Args:
        columns: List of column names
        column_types: Dictionary of column data types
        rows: List of data rows
        question: User question for context
        
    Returns:
        Tuple containing chart type and column mappings
    """
    # Count column types
    num_numeric = sum(1 for col_type in column_types.values() if col_type == "numeric")
    num_categorical = sum(1 for col_type in column_types.values() if col_type == "categorical")
    num_date = sum(1 for col_type in column_types.values() if col_type == "date")
    
    # Initialize column mappings
    chart_columns = {
        "x_axis": [],
        "y_axis": [],
        "series": [],
        "labels": []
    }
    
    # Rule 1: If we have date columns, prefer a line chart
    if num_date > 0 and num_numeric > 0:
        date_col = next(col for col, col_type in column_types.items() if col_type == "date")
        numeric_cols = [col for col, col_type in column_types.items() if col_type == "numeric"]
        
        chart_columns["x_axis"] = [date_col]
        chart_columns["y_axis"] = numeric_cols
        
        # If we have a categorical column, use it for series
        if num_categorical > 0:
            series_col = next(col for col, col_type in column_types.items() if col_type == "categorical")
            chart_columns["series"] = [series_col]
        
        return CHART_TYPE_LINE, chart_columns
    
    # Rule 2: If we have few categories and one numeric column, use a pie chart
    elif num_categorical == 1 and num_numeric == 1 and len(rows) <= 7:
        categorical_col = next(col for col, col_type in column_types.items() if col_type == "categorical")
        numeric_col = next(col for col, col_type in column_types.items() if col_type == "numeric")
        
        chart_columns["labels"] = [categorical_col]
        chart_columns["y_axis"] = [numeric_col]
        
        return CHART_TYPE_PIE, chart_columns
    
    # Rule 3: If we have categories and multiple numeric columns, use a bar/column chart
    elif num_categorical > 0 and num_numeric > 0:
        categorical_cols = [col for col, col_type in column_types.items() if col_type == "categorical"]
        numeric_cols = [col for col, col_type in column_types.items() if col_type == "numeric"]
        
        # Use the first categorical column for x-axis
        chart_columns["x_axis"] = [categorical_cols[0]]
        chart_columns["y_axis"] = numeric_cols
        
        # If we have another categorical column, use it for series
        if len(categorical_cols) > 1:
            chart_columns["series"] = [categorical_cols[1]]
        
        # If few rows, use a horizontal bar chart for better readability
        if len(rows) <= 5:
            return CHART_TYPE_BAR, chart_columns
        else:
            return CHART_TYPE_COLUMN, chart_columns
    
    # Default to enhanced table if no clear chart type is applicable
    return CHART_TYPE_TABLE, chart_columns

def _build_chart_config(
    chart_type: str, 
    chart_columns: Dict[str, List[str]], 
    columns: List[str], 
    rows: List[Dict[str, Any]], 
    question: str
) -> Dict[str, Any]:
    """
    Build complete chart configuration.
    
    Args:
        chart_type: Type of chart to generate
        chart_columns: Mapping of columns to chart components
        columns: List of all column names
        rows: List of data rows
        question: User question for context
        
    Returns:
        Complete chart configuration
    """
    # Extract chart title from question by removing question marks and making title case
    title = question.rstrip("?").capitalize()
    
    # Build basic config
    config = {
        "chart_type": chart_type,
        "chart_applicable": True,
        "title": title,
        "columns": chart_columns,
        "data": rows,
        "colors": _get_colors_for_chart(chart_type, len(chart_columns.get("y_axis", [])) or len(rows))
    }
    
    # Add chart-specific configurations
    if chart_type == CHART_TYPE_PIE:
        config["tooltip_format"] = "{point.percentage:.1f}%"
    elif chart_type in [CHART_TYPE_BAR, CHART_TYPE_COLUMN, CHART_TYPE_LINE]:
        config["stacked"] = len(chart_columns.get("series", [])) > 0
    
    return config


def _analyze_column_types(columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Analyze and determine the data type of each column.
    
    Args:
        columns: List of column names
        rows: List of data rows
        
    Returns:
        Dictionary mapping column names to data types
    """
    column_types = {}
    
    for col in columns:
        # Look at the first non-null value to determine type
        for row in rows:
            val = row.get(col)
            if val is not None:
                if isinstance(val, (int, float)):
                    column_types[col] = "numeric"
                elif isinstance(val, str):
                    # Check if it could be a date column based on name
                    if any(date_term in col.lower() for date_term in ["date", "year", "month", "quarter", "time", "period"]):
                        column_types[col] = "date"
                    else:
                        column_types[col] = "categorical"
                else:
                    column_types[col] = "unknown"
                break
        
        # If no non-null values found, mark as unknown
        if col not in column_types:
            column_types[col] = "unknown"
    
    return column_types


def _get_colors_for_chart(chart_type: str, num_colors: int) -> List[str]:
    """
    Get appropriate colors for the chart.
    
    Args:
        chart_type: Type of chart
        num_colors: Number of colors needed
        
    Returns:
        List of color hex codes
    """
    if chart_type == CHART_TYPE_PIE:
        # For pie charts, use a mix of all palettes
        colors = []
        palettes = ["blues", "ambers", "reds", "greens"]
        for i in range(num_colors):
            palette = palettes[i % len(palettes)]
            color_index = (i // len(palettes)) % len(COLOR_PALETTE[palette])
            colors.append(COLOR_PALETTE[palette][color_index])
        return colors
    
    elif chart_type == CHART_TYPE_LINE:
        # For line charts, prioritize blues and greens
        if num_colors <= len(COLOR_PALETTE["blues"]):
            return COLOR_PALETTE["blues"][:num_colors]
        else:
            return COLOR_PALETTE["blues"] + COLOR_PALETTE["greens"][:num_colors-len(COLOR_PALETTE["blues"])]
    
    elif chart_type in [CHART_TYPE_BAR, CHART_TYPE_COLUMN]:
        # For bar/column charts, use default palette for contrast
        if num_colors <= len(COLOR_PALETTE["default"]):
            return COLOR_PALETTE["default"][:num_colors]
        else:
            # Extend with colors from all palettes
            return COLOR_PALETTE["default"] + [
                color for palette in ["blues", "ambers", "reds", "greens"] 
                for color in COLOR_PALETTE[palette] 
                if color not in COLOR_PALETTE["default"]
            ][:num_colors-len(COLOR_PALETTE["default"])]
    
    # Default colors
    return COLOR_PALETTE["default"][:num_colors] if num_colors <= len(COLOR_PALETTE["default"]) else COLOR_PALETTE["default"]