import os
import time
import random
from pathlib import Path
from typing import Tuple, Dict, Any
from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "v1.md"
PROMPT_VERSION = "v1"

def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt file not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")

def get_client() -> OpenAI:
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1/")
    api_key = os.getenv("LLM_API_KEY", "ollama")
    # Set explicit 30.0s timeout and max_retries=0 so the SDK delegates retries to our custom loop
    return OpenAI(base_url=base_url, api_key=api_key, timeout=30.0, max_retries=0)

def call_llm_with_metrics(prompt_text: str) -> Tuple[str, Dict[str, Any]]:
    """Calls OpenAI-compatible endpoint with custom application-level retries, exponential backoff, and jitter."""
    client = get_client()
    model = os.getenv("LLM_MODEL", "gemma3:1b")
    system_prompt = load_system_prompt()

    max_attempts = 3  # Initial call + up to 2 retries
    base_delay = 1.0  # Seconds

    start_time = time.perf_counter()

    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.1
            )
            
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            raw_content = response.choices[0].message.content.strip()

            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            metrics = {
                "prompt_version": PROMPT_VERSION,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "duration_ms": duration_ms,
            }

            return raw_content, metrics

        except APIStatusError as e:
            # Fast-fail non-retryable client status codes (400, 401, 403) immediately on attempt 1
            if e.status_code in (400, 401, 403) or attempt == max_attempts - 1:
                raise e
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == max_attempts - 1:
                raise e

        # Exponential backoff (1s, 2s) + random jitter (0.0s - 0.5s)
        sleep_time = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
        time.sleep(sleep_time)

    raise RuntimeError("Unreachable retry loop state")

def call_llm_raw(content: str) -> Tuple[str, Dict[str, Any]]:
    user_prompt = f"Content to analyze:\n{content}"
    return call_llm_with_metrics(user_prompt)

def call_llm_repair(content: str, failed_output: str, error_msg: str) -> Tuple[str, Dict[str, Any]]:
    repair_prompt = (
        f"Content to analyze:\n{content}\n\n"
        f"Your previous response was invalid:\n{failed_output}\n\n"
        f"Error details:\n{error_msg}\n\n"
        f"Fix the error and output strictly valid JSON matching the required schema."
    )
    return call_llm_with_metrics(repair_prompt)