import json
from pathlib import Path
from datetime import datetime, timezone

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
QUARANTINE_FILE = LOGS_DIR / "quarantine.jsonl"

def quarantine_payload(content: str, raw_output: str, repair_output: str, error_msg: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_content": content,
        "initial_raw_output": raw_output,
        "repair_raw_output": repair_output,
        "validation_error": error_msg
    }
    with open(QUARANTINE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")