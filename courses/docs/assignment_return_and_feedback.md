# Assignment return and per-question feedback

This document describes the backend support for **returning an assignment to the student** (so they can edit and resubmit) and for **per-question feedback** that the student sees when viewing the assignment.

## Model: `AssignmentSubmission`

### `return_feedback` (JSONField, nullable)

- **When**: Set when a teacher **returns** a submitted (not yet graded) assignment to the student as draft. Also set by **TutorX** when autograding returns a submission for revision (score below passing; see `tutorx/ASSIGNMENT_SUBMISSION.md`).
- **Shape**: List of `{"question_id": "<uuid>", "feedback": "<string>"}`. Only entries with non-empty feedback need to be stored.
- **Usage**: When the student loads the lesson (e.g. optimized lesson CBV), the backend attaches this feedback to each assignment question so the frontend can show it for all question types (essay, short answer, fill-in-the-blank, code, etc.).

### `return_for_revision_count` (IntegerField, default 0)

- **When**: Used by **TutorX** only. Incremented each time the TutorX handler returns the submission for revision (draft + return_feedback). Not set or changed by the teacher return endpoint.
- **Purpose**: Together with **assignment.max_attempts**, caps how many times a submission can be returned. When `return_for_revision_count >= assignment.max_attempts`, the next TutorX submit is finalized as graded (pass or fail) with no further return.
- **Admin**: Exposed in AssignmentSubmission list and detail (Feedback fieldset) for tracing.

### `graded_questions` (JSONField)

- **When**: Set when the teacher **completes grading** (or when AI grading is saved). Also cleared when the teacher returns the assignment (reset to `[]`).
- **Shape**: List of objects with at least `question_id`, `points_earned`, and optionally `points_possible`, `feedback` / `teacher_feedback`, `correct_answer`.
- **Usage**: Teacher assignment overview and return dialog use this to pre-fill feedback and scores. Student does not receive graded_questions for a returned draft; they receive the same data via `return_feedback` attached to questions.

---

## Return endpoint (teacher)

**POST** `/api/teacher/assignments/{assignment_id}/grading/{submission_id}/return/`

- **Purpose**: Return a submitted (not graded) assignment to the student so they can edit and resubmit. Clears grading progress.
- **Permissions**: Authenticated teacher who owns the assignment’s course.
- **Conditions**: Submission must exist, belong to the assignment, have `status == 'submitted'` and `is_graded == False`. If the assignment is already graded, return 400.

**Request body (optional)**

```json
{
  "graded_questions": [
    { "question_id": "<uuid>", "feedback": "Optional feedback for this question." }
  ]
}
```

- Only `question_id` and `feedback` are required per item. `teacher_feedback` is accepted as an alias for `feedback`.
- Only items whose `question_id` belongs to the assignment are stored. Stored as `return_feedback` on the submission (list of `{question_id, feedback}`).

**Backend behavior**

1. Validate assignment, submission, and teacher.
2. Ensure submission is submitted and not graded.
3. Build `return_feedback` from `request.data.get('graded_questions')`: for each valid item, append `{question_id, feedback}` (feedback from `feedback` or `teacher_feedback`).
4. Set submission: `status='draft'`, `is_graded=False`, clear grading fields (`points_earned`, `points_possible`, `graded_at`, etc.), `graded_questions=[]`, `return_feedback=<built list or None>`.
5. Save and return submission in response.

**View**: `teacher/views.py` → `AssignmentReturnSubmissionView`.

---

## Student lesson: attaching return feedback to questions

When the student loads a lesson that includes an assignment and they have a **draft** submission with **return_feedback**:

1. **Optimized lesson (e.g. student lesson CBV)**  
   In `courses/views.py`, when building `assignment_data['questions']` for the response:
   - If the latest submission is draft and has non-empty `return_feedback`, call `_attach_return_feedback_to_questions(assignment_data['questions'], latest.return_feedback)`.
   - This adds `feedback` and `has_feedback` to each question so the frontend can show teacher feedback for every question type.

2. **Helpers** (`student/views.py`)
   - **`_submission_has_return_feedback(submission)`**: Returns True when `submission.status == 'draft'` and `submission.return_feedback` is a non-empty list.
   - **`_attach_return_feedback_to_questions(questions_data, return_feedback)`**: Builds a lookup from `return_feedback` (question_id → feedback), then for each question in `questions_data` sets `feedback` and `has_feedback`. Returns a new list of question dicts.

So the student never receives `graded_questions` for a returned draft; they receive the same feedback via **questions with `feedback` and `has_feedback`** in the lesson payload.

---

## Teacher assignment overview (for return dialog)

The teacher assignment overview (e.g. student submissions list / assignment detail) must include for each submission:

- **`questions`**: List of assignment questions with at least `id`, `order`, `points_possible` so the frontend can list questions and compute pass/fail for default “include feedback” (e.g. below half = include).
- **`graded_questions`**: List of `{question_id, points_earned, feedback?, teacher_feedback?, correct_answer?}` from the last time the teacher (or AI) graded this submission. Used to pre-fill the return dialog and show scores. When the teacher then clicks “Return”, the frontend sends a subset of these as `graded_questions` in the return request body; the backend stores that as `return_feedback` on the submission.

---

## Summary

| Concept | Backend | Frontend use |
|--------|---------|--------------|
| Return submission | POST `.../return/` with `graded_questions` → stored as `return_feedback` | Teacher Return dialog builds payload via `assignmentReturnFeedback.ts` |
| Student sees feedback | Lesson API attaches `return_feedback` to each question (`feedback`, `has_feedback`) | AssignmentDetailView shows “Teacher feedback” for all question types when `currentQuestion.feedback` is set |
| Teacher overview | Submission includes `graded_questions` and `questions` | Return dialog pre-fills and computes defaults (failed = include by default) |
