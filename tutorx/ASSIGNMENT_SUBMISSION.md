# TutorX assignment submission (autograde and return for revision)

When a student submits an assignment whose lesson type is **TutorX**, the student submission view delegates to the TutorX app to autograde and optionally return for revision. This document describes the backend flow.

## Entry point

- **Student submit**: `POST /api/student/assignments/{assignment_id}/submit/` (see `student/views.py` → `AssignmentSubmissionView`).
- After the submission is saved (non-draft), the view checks whether the assignment has a lesson with `type == 'tutorx'`. If yes, it calls:
  - `from tutorx.services.assignment_submission import handle_assignment_submission`
  - `handle_assignment_submission(submission)`
- The submission is then refreshed and the response returned to the frontend. No separate API for TutorX; the same submit endpoint is used.

## Handler: `tutorx/services/assignment_submission.py`

**`handle_assignment_submission(submission)`**

- **Input**: An `AssignmentSubmission` instance (already saved with `status='submitted'`).
- **Output**: None. The submission is updated in place (status, grading fields, or return_feedback).

### Steps

1. **Idempotency**: If `submission.is_graded` is already True, return immediately (do not re-grade).
2. **Load assignment and answers**: `assignment = submission.assignment`, `answers = submission.answers`.
3. **AI grading**: Build list of questions that need AI (essay, fill_blank, short_answer without correct_answer). Call `GeminiGrader().grade_questions_batch(ai_questions, assignment_context)` (same as teacher AI-grade). Merge with local scoring for MC, true/false, short_answer with key.
4. **Scores**: Compute `total_score`, `total_possible`, `percentage`, and `passed = (percentage >= assignment.passing_score)`.
5. **Max returns**: Read `assignment.max_attempts` as the maximum number of times this submission may be **returned for revision**. Read `submission.return_for_revision_count` (default 0). If `not passed` and `return_count >= max_returns`, do **not** return again; treat as **finalize graded** (see below).
6. **If passed (or at max returns)** → **Graded path**:
   - Set `status='graded'`, `is_graded=True`, `points_earned`, `points_possible`, `percentage`, `passed` (True if actually passed, False if finalizing after max returns), `graded_at`, `graded_questions`, `return_feedback=None`.
   - Save with `update_fields=[...]`.
   - Call `enrollment.update_assignment_performance(percentage, is_graded=True)`.
7. **If not passed and return_count < max_returns** → **Return for revision**:
   - Set `status='draft'`, `is_graded=False`, clear grading fields, set `return_feedback` (list of `{question_id, feedback}` from grades).
   - Set `submission.return_for_revision_count = return_count + 1`.
   - Save with `update_fields=[..., 'return_for_revision_count']`.

The same `return_feedback` and lesson API behavior used for teacher returns apply: the student sees feedback on questions when they reopen the assignment (see [Assignment return and feedback](../courses/docs/assignment_return_and_feedback.md)).

## Model: `AssignmentSubmission` (courses app)

- **`return_for_revision_count`** (IntegerField, default 0): Number of times this submission has been returned for revision by TutorX. Incremented each time the handler takes the “return for revision” path. Used with `assignment.max_attempts` to cap returns; when `return_for_revision_count >= assignment.max_attempts`, the next submit is always finalized as graded (pass or fail).

## Admin

- **AssignmentSubmission** (Django Admin): `return_for_revision_count` is in `list_display` and in the Feedback fieldset so you can trace how many times a submission was returned.

## Summary

| Scenario                         | Action                                      |
|----------------------------------|---------------------------------------------|
| Score ≥ passing_score            | Mark graded (pass), save, update enrollment |
| Score < passing_score, returns left | Return for revision (draft + return_feedback), increment return_for_revision_count |
| Score < passing_score, no returns left | Finalize as graded (fail), no further returns |

Grading uses the same logic as teacher AI-grade: `GeminiGrader().grade_questions_batch()` and the same `graded_questions` shape. Return feedback shape matches the teacher return endpoint so the frontend shows it the same way.
