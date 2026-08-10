# AI Service platform (Phase 1)

Jobeasy-style platform app for Little Learners Tech.

## Concepts

| Term | Meaning |
|------|--------|
| **AIModel** | Provider + model id (gemini / openai / deepseek) |
| **AIService** | One product capability with its own prompts (slug) |
| **AIPromptConfiguration** | System prompt + model + temperature for a service variant |
| **gateway.resolve_model** | Builds a Pydantic AI `Model` from a prompt config or overrides |

## Phase 1 status

- Catalog models + Admin
- `resolve_model()` gateway (Gemini Vertex/API key, OpenAI, DeepSeek)
- `python manage.py setup_ai_models` seed
- Playground runners land in Phase 2–3
- Study Coach wiring in Phase 4

## Switching models

1. Prefer Admin → **AI models** / **AI Prompt Configurations** (attach `ai_model` to a prompt).
2. Env fallbacks when a prompt has no model:

```
AI_SERVICE_DEFAULT_PROVIDER=gemini
AI_SERVICE_GEMINI_MODEL=gemini-2.5-flash
AI_SERVICE_OPENAI_MODEL=gpt-4o-mini
AI_SERVICE_DEEPSEEK_MODEL=deepseek-chat
AI_SERVICE_DEFAULT_TEMPERATURE=0.4
```

## Keys

| Provider | Env |
|----------|-----|
| Gemini (Vertex) | `GCP_PROJECT_ID`, `VERTEX_AI_LOCATION`, ADC / `GOOGLE_APPLICATION_CREDENTIALS` |
| Gemini (API) | `GEMINI_API_KEY` or `GOOGLE_API_KEY` + `AI_SERVICE_GEMINI_USE_VERTEX=false` |
| OpenAI | `OPENAI_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |

## Seed models

```bash
python manage.py migrate ai_service
python manage.py setup_ai_models
```
