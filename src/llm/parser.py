import json
import re
from pydantic import ValidationError
from src.llm.schema import EnrichResponse

def clean_json_text(raw_text: str) -> str:
    """Strips markdown code fences and extraneous whitespace."""
    text = raw_text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

def parse_and_validate(raw_text: str) -> EnrichResponse:
    """Cleans, parses JSON, and validates against EnrichResponse schema."""
    cleaned = clean_json_text(raw_text)
    data = json.loads(cleaned)
    return EnrichResponse(**data)