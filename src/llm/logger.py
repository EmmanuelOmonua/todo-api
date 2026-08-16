import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger("llm_metrics")
logger.setLevel(logging.INFO)

# Standard stdout handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)

def log_llm_call(metrics: dict, repaired: bool = False, success: bool = True) -> None:
    log_entry = {
        "event": "llm_call",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": metrics.get("prompt_version", "v1"),
        "model": metrics.get("model", "unknown"),
        "input_tokens": metrics.get("prompt_tokens", 0),
        "output_tokens": metrics.get("completion_tokens", 0),
        "duration_ms": metrics.get("duration_ms", 0),
        "repaired": repaired,
        "success": success
    }
    logger.info(json.dumps(log_entry))