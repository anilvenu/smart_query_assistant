from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from datetime import datetime

def run_query(sql: str, db: Session):
    try:
        result = db.execute(text(sql))
        rows = result.fetchall()
        columns = list(result.keys())  # Convert RMKeyView to a list

        # Convert Decimal, DateTime, and other non-serializable types
        def convert_value(value):
            if isinstance(value, Decimal):
                return float(value)  # Convert Decimal to float
            elif isinstance(value, datetime):
                return value.isoformat()  # Convert datetime to ISO 8601 string
            return value  # Return other types as they are (e.g., int, str)

        data = [
            {col: convert_value(r[i]) for i, col in enumerate(columns)} 
            for r in rows
        ]
        
        return {
            "columns": columns,
            "rows": data
        }
    except Exception as e:
        raise RuntimeError(f"Error executing query: {e}")
