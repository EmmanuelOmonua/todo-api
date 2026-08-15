from enum import Enum
from typing import List
from pydantic import BaseModel, Field

class CategoryEnum(str, Enum):
    TECH = "tech"
    FINANCE = "finance"
    NEWS = "news"
    EDUCATION = "education"
    OTHER = "other"

class EnrichRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=10,
        max_length=4000,
        description="Raw scraped text content to enrich"
    )

class EnrichResponse(BaseModel):
    category: CategoryEnum
    summary: str
    quality_flags: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)