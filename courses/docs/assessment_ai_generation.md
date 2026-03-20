# Assessment AI Generation

## Overview

Assessment AI generation supports explicit per-question-type counts and requires exact type distribution in generated output.

The backend flow is:
1. `courses/views.py` receives generation request and reads type counts.
2. `GeminiAssessmentService.generate()` builds prompt + structured schema call.
3. Response is normalized/validated by question type before returning to frontend.

## Request Fields

Expected count fields:
- `total_questions`
- `multiple_choice_count`
- `true_false_count`
- `fill_blank_count`
- `short_answer_count`
- `essay_count`
- `code_count`

`code_count` is required for reliable code question generation. If omitted or zero, code questions are not guaranteed.

## Prompt and Type Enforcement

`GeminiAssessmentService` includes:
- explicit "Exactly N ... question(s)" requirements for each selected type
- code-specific prompt instructions when `code_count > 0`:
  - generate executable programming tasks
  - include `content.language` (default python if uncertain)
  - include `content.instructions`
  - include `content.starter_code` (empty string allowed)

## Structured Schema

`ai/schemas.py` assessment schema supports:
- `type: "code"` in enum
- code `content` properties:
  - `language`
  - `instructions`
  - `starter_code`

## Validation Defaults

During post-processing, backend ensures code question content is well-formed:
- `language` defaults to `"python"` if missing
- `instructions` defaults to `""` if missing
- `starter_code` defaults to `""` if missing

## Common Failure Modes

- Code selected in UI but not generated:
  - `code_count` not sent from frontend, or
  - backend view not forwarding `code_count`
- Wrong number of code questions:
  - prompt not enforcing exact type counts, or
  - redistribution logic not including `code_count`
