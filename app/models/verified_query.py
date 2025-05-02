"""
Data classes for working with verified queries,
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

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
