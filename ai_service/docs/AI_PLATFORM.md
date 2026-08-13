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

## Phase 2 — Admin playground

Admin → **AI Gateway Playgrounds**:

1. Create / open a row
2. Optionally pick an **AI Prompt Configuration** (model + system prompt)
3. Edit **user message**
4. Click **Run gateway probe** (AJAX — does not require Save first)
5. Inspect JSON result; **Save last run to record** to persist snapshots

Shared pieces for Phase 3+ service playgrounds:

- Mixin: `ai_service/admin_playground.py` (`AIPlaygroundAdminMixin`)
- Widget template: `templates/admin/ai_service/_playground_run_widget.html`
- Runner return contract: `{ success, error, result, provider, model_id, temperature, instruction_slug, raw_text }`

```bash
python manage.py migrate ai_service
```

## Phase 3 — `study_coach_deck` AI Service

```bash
python manage.py setup_ai_models
python manage.py setup_study_coach_deck
python manage.py migrate ai_service
```

Admin → **Study Coach Deck Playgrounds**:

1. Set lesson title (+ optional grounding text)
2. Pick difficulty / card count / prompt config
3. **Generate study deck**
4. Inspect `result.cards` JSON (hints, options, answers)
5. **Save last run to record**

Runner used by Admin (and Phase 4 product):

`ai_service.runners.study_coach_deck.generate_study_coach_deck(...)`

Gemini local tip: with `GEMINI_API_KEY` set, the gateway uses the Developer API (not Vertex) unless `AI_SERVICE_GEMINI_USE_VERTEX=true`.

## Logging & Slack alerts (ops)

Every runner logs the resolved model at **INFO** (stdout via the `ai_service` logger):

```
INFO ai_service.run service=study_coach_deck provider=gemini model=gemini-2.5-flash temperature=0.4 ...
```

Failures are classified with `ai_service.exceptions.AIServiceError` / `from_exception(...)` (e.g. **429 / quota → `rate_limited`**), then sent through `notify_and_classify` → `error_alerts.notify_ai_failure` → **`SLACK_ERROR_ALERTS`** (throttled).

Helpers:

- `ai_service.alerts.log_run_model`
- `ai_service.alerts.notify_and_classify`

Set `SLACK_ERROR_ALERTS` in `.env` (same channel as other AI/app error alerts).

## Phase 4 — Study Coach product wiring

Student Tools → Study Coach → **Generate quiz** calls:

`studycoach.services.deck_generator.generate_deck_for_lesson` → `generate_study_coach_deck`

- Grounding from lesson `description` only (HTML stripped; else title-only).
- Book pages for the lesson are passed as a **catalog** (id, page number, title, short excerpt). The model cites `source_page_id`; the server validates it and stores `{ material_id, page, title }`. The frontend builds the student page URL. The model never invents URLs.
- Every card gets a short `explanation` (prompt-required; server fills a fallback if missing).
- Prompt variants: keep original slug `default` unchanged; `math_display` is the active default (column math via `display_json` string + LaTeX). Re-run `setup_study_coach_deck` to seed/update `math_display` without overwriting `default`.
- Short-answer **Check** uses a separate service, `study_coach_grade` (`python manage.py setup_study_coach_grade`). Default model is **Gemini 2.5 Flash Lite** (falls back to Flash, then DeepSeek). Same grading intent as assignment GeminiGrader (meaning over exact wording), tiny `{correct, feedback}` output, 20s timeout.
- **No static fallback.** On failure the API returns:
  `{"error": "We couldn't complete that AI request right now. Please try again.", "error_code": "..."}`
  with HTTP 429 (rate limited) or 503.

## Phase 5 — Production hardening

### Retries & timeouts

| Knob | Default | Meaning |
|------|---------|---------|
| `AI_SERVICE_HTTP_TIMEOUT` | 60 | Per-request httpx / ModelSettings timeout (seconds) |
| `AI_SERVICE_HTTP_CONNECT_TIMEOUT` | 10 | Connect timeout |
| `AI_SERVICE_HTTP_RETRY_ATTEMPTS` | 3 | Total attempts for 429/5xx + connect errors |
| `AI_SERVICE_RUN_TIMEOUT` | 90 | Wall-clock budget for full `agent.run_sync` |

HTTP retries honor `Retry-After` when present (capped).

### Logging

On each run:

```
INFO ai_service.run service=… provider=… model=…
INFO ai_service.run.finished service=… provider=… model=… success=True latency_ms=1234 grounding_mode=title
```

Failures are classified and sent to `SLACK_ERROR_ALERTS` (throttled). Study Coach never returns static cards — students see a friendly try-again message.

### Deploy / seeds

```bash
python manage.py migrate
python manage.py setup_ai_models
python manage.py setup_study_coach_deck
python manage.py setup_study_coach_grade
```

Or set `AI_SERVICE_SEED_ON_STARTUP=true` so `entrypoint.sh` runs the setup commands after migrate (idempotent).

