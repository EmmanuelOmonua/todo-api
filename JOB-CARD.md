# Job Card: Scraped Record Enrichment

**What it does:** Enriches raw text/scraped records into a structured summary, category, and quality flags.

**Input:** 
```json
{
  "content": "string, 10-4000 characters"
}

Output:

{
  "category": "one of [tech|finance|news|education|other]",
  "summary": "one concise sentence summarizing the main point",
  "quality_flags": ["list of flags, e.g. 'missing_author', 'short_content', etc."],
  "confidence": 0.0-1.0
}

It must never:
- Invent a category outside the allowed list.  
- Return free-text outside the JSON structure.  
- Include unvalidated or raw model strings.  

When unsure:
- Return category "other" with confidence below 0.5.  

---

## 3. Environment Variables (`.env`)

Add these variables to your `.env` (and add dummy versions to `.env.example`):

```bash
# OpenRouter settings (or Ollama http://localhost:11434/v1/ with key "ollama")
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-actual-openrouter-key
LLM_MODEL=openrouter/free

# Control Flags
LLM_STUB=1
LLM_ENABLED=true