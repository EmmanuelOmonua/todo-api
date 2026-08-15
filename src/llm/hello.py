import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Retrieve variables with explicit Ollama defaults
base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1/")
api_key = os.getenv("LLM_API_KEY", "ollama")
model = os.getenv("LLM_MODEL", "gemma3:1b")

client = OpenAI(
    base_url=base_url,
    api_key=api_key
)

res = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
)

print("Model Output:", res.choices[0].message.content)