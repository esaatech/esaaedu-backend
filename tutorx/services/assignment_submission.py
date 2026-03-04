"""
TutorX assignment submission handler.

When a student submits an assignment whose lesson type is TutorX, the student
submission view delegates here. Phase 2: no-op. Phase 3: autograde via GeminiGrader.
Phase 4: if score >= passing_score mark graded; else return for revision (draft + return_feedback).

Contract:
- Input: submission (AssignmentSubmission, saved with status='submitted').
- Return: None.
"""
from decimal import Decimal
from django.utils import timezone


def _normalize_student_answer(value):
    """Extract string from submission.answers entry (may be string or dict with text/content)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return (value.get("text") or value.get("content") or "").strip() or str(value)
    return str(value).strip()


def _build_questions_for_ai(assignment, submission):
    """
    Build list of question dicts for GeminiGrader (same shape as teacher AI-grade).
    Only essay, fill_blank, short_answer (without correct_answer); only questions with an answer.
    """
    answers = submission.answers or {}
    questions = []
    for q in assignment.questions.all():
        qid_str = str(q.id)
        if qid_str not in answers:
            continue
        needs_ai = q.type in ("essay", "fill_blank", "short_answer")
        if q.type == "short_answer" and (q.content or {}).get("correct_answer"):
            needs_ai = False
        if not needs_ai:
            continue
        student_answer = _normalize_student_answer(answers.get(qid_str))
        if not student_answer:
            continue
        content = q.content or {}
        questions.append({
            "question_id": qid_str,
            "question_text": q.question_text or "",
            "question_type": q.type,
            "student_answer": student_answer,
            "points_possible": q.points,
            "explanation": (q.explanation or "").strip() or None,
            "rubric": content.get("rubric"),
        })
    return questions


def _score_non_ai_question(question, student_answer_str):
    """
    Score multiple_choice, true_false, short_answer (with correct_answer).
    Returns (points_earned, points_possible). points_possible from question.points.
    """
    points_possible = question.points or 1
    content = question.content or {}
    correct_answer = content.get("correct_answer")
    if correct_answer is not None:
        # Normalize for comparison
        correct = str(correct_answer).strip().lower()
        given = (student_answer_str or "").strip().lower()
        if correct == given:
            return (points_possible, points_possible)
        return (0, points_possible)
    # Options with correct flag (e.g. multiple_choice)
    options = content.get("options") or []
    for opt in options:
        if opt.get("correct") is True:
            opt_id = str(opt.get("id", opt.get("text", "")))
            if (student_answer_str or "").strip() == opt_id or (student_answer_str or "").strip() == str(opt.get("text", "")):
                return (points_possible, points_possible)
            break
    return (0, points_possible)


def _build_assignment_context(assignment):
    """Build context dict from first lesson (same as teacher AI-grade view)."""
    first_lesson = assignment.lessons.first()
    if not first_lesson:
        return {"assignment_title": assignment.title, "assignment_description": assignment.description or ""}
    context = {
        "lesson_title": first_lesson.title,
        "assignment_title": assignment.title,
        "assignment_description": assignment.description or "",
    }
    if hasattr(first_lesson, "content") and first_lesson.content:
        context["lesson_content"] = first_lesson.content
    if hasattr(first_lesson, "description") and first_lesson.description:
        context["lesson_description"] = first_lesson.description
    if first_lesson.course:
        context["course_title"] = first_lesson.course.title
    return context


def handle_assignment_submission(submission):
    """
    Process a TutorX assignment submission.

    Phase 3: Grade via GeminiGrader (AI questions) + local scoring (MC/TF/short_answer with key).
    Phase 4: If percentage >= assignment.passing_score -> graded; else -> return for revision (draft + return_feedback).
    """
    print(f"[TutorX] ENTER submission_id={submission.id} assignment_id={submission.assignment_id} is_graded={submission.is_graded} status={submission.status}")

    # Idempotency: do not re-grade if already graded
    if submission.is_graded:
        print("[TutorX] submission already graded, skipping EXIT")
        return

    assignment = submission.assignment
    answers = submission.answers or {}
    questions_list = list(assignment.questions.all())
    print(f"[TutorX] assignment questions count={len(questions_list)} answer keys={list(answers.keys()) if answers else []}")
    if not questions_list:
        print("[TutorX] assignment has no questions, skipping EXIT")
        return

    # 1) Build and run AI grading for essay / fill_blank / short_answer (no key)
    ai_questions = _build_questions_for_ai(assignment, submission)
    print(f"[TutorX] ai_questions count={len(ai_questions)}")
    grade_by_qid = {}
    total_score = 0
    total_possible = 0

    # Map question_id -> points_possible for AI questions (Gemini grade items don't include points_possible)
    ai_points_possible = {q["question_id"]: (q.get("points_possible") or 1) for q in ai_questions}

    if ai_questions:
        try:
            print(f"[TutorX] calling GeminiGrader.grade_questions_batch with {len(ai_questions)} questions")
            from ai.gemini_grader import GeminiGrader
            grader = GeminiGrader()
            assignment_context = _build_assignment_context(assignment)
            result = grader.grade_questions_batch(ai_questions, assignment_context)
            print(f"[TutorX] GeminiGrader returned grades count={len(result.get('grades', []))} total_score={result.get('total_score')} total_possible={result.get('total_possible')}")
            for g in result.get("grades", []):
                qid = str(g.get("question_id", ""))
                if not qid:
                    continue
                points_earned = g.get("points_earned", 0)
                points_possible = g.get("points_possible") or ai_points_possible.get(qid, 1)
                grade_by_qid[qid] = {
                    "points_earned": points_earned,
                    "points_possible": points_possible,
                    "feedback": g.get("feedback") or "",
                    "correct_answer": g.get("correct_answer"),
                }
                total_score += points_earned
                total_possible += points_possible
        except Exception as e:
            print(f"[TutorX] GeminiGrader FAILED: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to 0 for AI questions so we still apply return/graded logic
            for q in ai_questions:
                qid = q.get("question_id")
                pts = q.get("points_possible", 0)
                grade_by_qid[qid] = {
                    "points_earned": 0,
                    "points_possible": pts,
                    "feedback": f"Grading unavailable: {e}.",
                    "correct_answer": None,
                }
                total_possible += pts

    # 2) Score non-AI questions (multiple_choice, true_false, short_answer with correct_answer)
    for q in questions_list:
        qid_str = str(q.id)
        if qid_str in grade_by_qid:
            continue
        pts_poss = q.points or 1
        student_answer = _normalize_student_answer(answers.get(qid_str))
        earned, poss = _score_non_ai_question(q, student_answer)
        grade_by_qid[qid_str] = {
            "points_earned": earned,
            "points_possible": poss,
            "feedback": "",
            "correct_answer": None,
        }
        total_score += earned
        total_possible += poss

    if total_possible <= 0:
        print("[TutorX] total_possible is 0, skipping EXIT")
        return

    percentage = float(Decimal(total_score) / Decimal(total_possible) * 100)
    passing_score = getattr(assignment, "passing_score", 70) or 70
    passed = percentage >= passing_score

    # Cap returns: use assignment.max_attempts as max number of "return for revision". After that, finalize as graded (pass or fail).
    max_returns = getattr(assignment, "max_attempts", 1) or 1
    return_count = getattr(submission, "return_for_revision_count", None)
    if return_count is None:
        return_count = 0
    finalize_graded = passed or (return_count >= max_returns)
    if not passed and return_count >= max_returns:
        print(f"[TutorX] max returns reached (return_count={return_count} max_returns={max_returns}), finalizing as graded (failed)")

    print(f"[TutorX] total_score={total_score} total_possible={total_possible} percentage={percentage} passing_score={passing_score} passed={passed} finalize_graded={finalize_graded} return_count={return_count} max_returns={max_returns}")

    # Build graded_questions in same shape as teacher (AssignmentGradingSerializer)
    graded_questions = []
    for q in questions_list:
        qid_str = str(q.id)
        g = grade_by_qid.get(qid_str)
        if not g:
            continue
        graded_questions.append({
            "question_id": qid_str,
            "points_earned": g["points_earned"],
            "points_possible": g["points_possible"],
            "teacher_feedback": g.get("feedback") or "",
            "correct_answer": g.get("correct_answer"),
        })

    if finalize_graded:
        # Phase 3: mark as graded (or finalize after max returns with passed=False)
        print(f"[TutorX] applying GRADED path submission_id={submission.id}")
        submission.status = "graded"
        submission.is_graded = True
        submission.is_teacher_draft = False
        submission.points_earned = Decimal(total_score)
        submission.points_possible = Decimal(total_possible)
        submission.percentage = round(Decimal(percentage), 2)
        submission.passed = bool(passed)
        submission.graded_at = timezone.now()
        submission.graded_by = None
        submission.instructor_feedback = ""
        submission.graded_questions = graded_questions
        submission.return_feedback = None
        print(f"[TutorX] saving submission as graded (update_fields) submission_id={submission.id}")
        submission.save(update_fields=[
            "status", "is_graded", "is_teacher_draft", "points_earned", "points_possible",
            "percentage", "passed", "graded_at", "graded_by", "instructor_feedback",
            "graded_questions", "return_feedback",
        ])
        try:
            enrollment = submission.enrollment
            enrollment.update_assignment_performance(float(percentage), is_graded=True)
        except Exception as e:
            print(f"[TutorX] update_assignment_performance failed: {e}")
        print(f"[TutorX] submission saved as GRADED submission_id={submission.id}")
    else:
        # Phase 4: return for revision (same shape as teacher return); increment return count
        submission.return_for_revision_count = return_count + 1
        print(f"[TutorX] applying RETURN FOR REVISION path submission_id={submission.id} return_for_revision_count={submission.return_for_revision_count}")
        return_feedback = [
            {"question_id": qid, "feedback": grade_by_qid.get(qid, {}).get("feedback") or ""}
            for qid in grade_by_qid
        ]
        return_feedback = [x for x in return_feedback if x.get("feedback")]
        if not return_feedback:
            return_feedback = None
        submission.status = "draft"
        submission.is_graded = False
        submission.is_teacher_draft = False
        submission.points_earned = None
        submission.points_possible = None
        submission.percentage = None
        submission.passed = False
        submission.graded_at = None
        submission.graded_by = None
        submission.instructor_feedback = ""
        submission.graded_questions = []
        submission.return_feedback = return_feedback
        print(f"[TutorX] saving submission as return for revision (update_fields) submission_id={submission.id}")
        submission.save(update_fields=[
            "status", "is_graded", "is_teacher_draft", "points_earned", "points_possible",
            "percentage", "passed", "graded_at", "graded_by", "instructor_feedback",
            "graded_questions", "return_feedback", "return_for_revision_count",
        ])
        print(f"[TutorX] submission saved as RETURN FOR REVISION submission_id={submission.id} percentage={percentage} passing_score={passing_score}")

    print(f"[TutorX] EXIT submission_id={submission.id}")
