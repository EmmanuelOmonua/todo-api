import os
from pathlib import Path
from openai import OpenAI

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "v1.md"

def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt file not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")

def call_llm_raw(content: str) -> str:
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1/")
    api_key = os.getenv("LLM_API_KEY", "ollama")
    model = os.getenv("LLM_MODEL", "gemma3:1b")

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=15.0)
    system_prompt = load_system_prompt()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Content to analyze:\n{content}"}
        ],
        temperature=0.1
    )

    return response.choices[0].message.content.strip()