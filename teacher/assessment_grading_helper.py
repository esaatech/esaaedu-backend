"""
Hybrid grading for course assessments (tests/exams) only.

- Deterministic scoring for objective / structured types when `content` supports it.
- Falls back to Gemini (assessment_grading template) for essay, code, and ambiguous cases.

Does not modify assignment AI grading (see teacher.ai_grading_helper / AssignmentAIGradingView).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _parse_json_if_string(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if s.startswith(("{", "[")):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return value
    return value


def _student_to_list(value: Any) -> Optional[List[Any]]:
    value = _parse_json_if_string(value)
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return parts if parts else ([] if not value.strip() else [value.strip()])
    return None


def _mcq_correct_answer(content: Dict[str, Any]) -> Optional[str]:
    ca = content.get("correct_answer")
    if ca is not None and str(ca).strip():
        return str(ca).strip()
    fo = content.get("full_options") or {}
    opts = fo.get("options") if isinstance(fo, dict) else None
    if isinstance(opts, list):
        for o in opts:
            if isinstance(o, dict) and o.get("isCorrect") and o.get("text") is not None:
                return str(o["text"]).strip()
    return None


def _try_grade_multiple_choice(
    content: Dict[str, Any], student_answer: Any, points_possible: float
) -> Optional[Dict[str, Any]]:
    correct = _mcq_correct_answer(content)
    if correct is None:
        return None
    earned = float(points_possible) if _norm_text(student_answer) == _norm_text(correct) else 0.0
    return {
        "points_earned": earned,
        "points_possible": float(points_possible),
        "feedback": (
            "You selected the correct answer."
            if earned
            else "This answer is incorrect. Review the question and the options."
        ),
        "correct_answer": correct,
        "confidence": 1.0,
    }


def _try_grade_true_false(
    content: Dict[str, Any], student_answer: Any, points_possible: float
) -> Optional[Dict[str, Any]]:
    ca = content.get("correct_answer")
    if ca is None:
        return None
    c = str(ca).strip().lower()
    if c not in ("true", "false"):
        return None
    s = str(student_answer).strip().lower()
    if s not in ("true", "false"):
        return None
    earned = float(points_possible) if s == c else 0.0
    return {
        "points_earned": earned,
        "points_possible": float(points_possible),
        "feedback": "Correct." if earned else f"The correct answer is {c}.",
        "correct_answer": c,
        "confidence": 1.0,
    }


def _try_grade_short_answer(
    content: Dict[str, Any], student_answer: Any, points_possible: float
) -> Optional[Dict[str, Any]]:
    key = content.get("correct_answer")
    if key is None or (isinstance(key, str) and not key.strip()):
        return None
    accept_variations = content.get("accept_variations", True)
    s = str(student_answer).strip()
    k = str(key).strip()
    if accept_variations:
        match = _norm_text(s) == _norm_text(k)
    else:
        match = s == k
    earned = float(points_possible) if match else 0.0
    return {
        "points_earned": earned,
        "points_possible": float(points_possible),
        "feedback": "Your answer matches the expected response." if earned else "Your answer does not match the expected response.",
        "correct_answer": k,
        "confidence": 1.0,
    }


def _fill_blank_correct_map(content: Dict[str, Any]) -> Optional[Dict[int, str]]:
    raw = content.get("correct_answers")
    if raw is None:
        ca = content.get("correct_answer")
        if ca is not None and str(ca).strip():
            return {0: str(ca).strip()}
        return None
    if isinstance(raw, dict):
        out: Dict[int, str] = {}
        for k, v in raw.items():
            try:
                idx = int(k)
            except (TypeError, ValueError):
                continue
            out[idx] = str(v).strip()
        return out if out else None
    if isinstance(raw, list):
        return {i: str(x).strip() for i, x in enumerate(raw) if str(x).strip()}
    return None


def _try_grade_fill_blank(
    content: Dict[str, Any], student_answer: Any, points_possible: float
) -> Optional[Dict[str, Any]]:
    cmap = _fill_blank_correct_map(content)
    if not cmap:
        return None
    parts = _student_to_list(student_answer)
    if parts is None:
        parts = []
    if isinstance(student_answer, str) and not student_answer.strip():
        parts = []
    elif isinstance(student_answer, str) and "," not in student_answer and len(cmap) == 1:
        parts = [student_answer.strip()]

    max_idx = max(cmap.keys())
    n_blanks = max_idx + 1
    correct = 0
    details = []
    for i in range(n_blanks):
        exp = cmap.get(i)
        if exp is None:
            continue
        got = parts[i] if i < len(parts) else ""
        ok = _norm_text(got) == _norm_text(exp) if exp else False
        if ok:
            correct += 1
        details.append((i, exp, got, ok))
    if not details:
        return None
    ratio = correct / len(details)
    earned = round(float(points_possible) * ratio, 4)
    wrong_bits = [f"Blank {i+1}: expected '{e}', you wrote '{g}'." for i, e, g, ok in details if not ok]
    feedback = "All blanks are correct." if ratio >= 1.0 else " ".join(wrong_bits) or "Some blanks need correction."
    model = ", ".join(cmap.get(j, "") for j in range(n_blanks))
    return {
        "points_earned": earned,
        "points_possible": float(points_possible),
        "feedback": feedback,
        "correct_answer": model,
        "confidence": 1.0,
    }


def _ordering_correct_sequence(content: Dict[str, Any]) -> Optional[List[str]]:
    seq = content.get("correct_order")
    if isinstance(seq, list) and seq:
        return [str(x).strip() for x in seq]
    items = content.get("items")
    if isinstance(items, list) and items:
        if all(isinstance(x, dict) and "text" in x for x in items):
            ordered = sorted(items, key=lambda x: int(x.get("order", 0)))
            return [str(x["text"]).strip() for x in ordered]
    return None


def _try_grade_ordering(
    content: Dict[str, Any], student_answer: Any, points_possible: float
) -> Optional[Dict[str, Any]]:
    correct = _ordering_correct_sequence(content)
    if not correct:
        return None
    student = _student_to_list(student_answer)
    if student is None:
        student = []
    student = [str(x).strip() for x in student]
    if len(student) != len(correct):
        return None
    matches = sum(1 for a, b in zip(student, correct) if _norm_text(a) == _norm_text(b))
    ratio = matches / len(correct) if correct else 0.0
    earned = round(float(points_possible) * ratio, 4)
    feedback = (
        "Items are in the correct order."
        if ratio >= 1.0
        else f"{matches} of {len(correct)} positions match the correct order."
    )
    return {
        "points_earned": earned,
        "points_possible": float(points_possible),
        "feedback": feedback,
        "correct_answer": " → ".join(correct),
        "confidence": 1.0,
    }


def _normalize_pairs(pairs: Any) -> Optional[List[Tuple[str, str]]]:
    if not isinstance(pairs, list) or not pairs:
        return None
    out: List[Tuple[str, str]] = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        left = p.get("left")
        right = p.get("right")
        if left is None or right is None:
            continue
        out.append((str(left).strip(), str(right).strip()))
    return out or None


def _try_grade_matching(
    content: Dict[str, Any], student_answer: Any, points_possible: float
) -> Optional[Dict[str, Any]]:
    correct_pairs = _normalize_pairs(content.get("pairs"))
    if not correct_pairs:
        return None
    student = _parse_json_if_string(student_answer)
    if not isinstance(student, list):
        student = _student_to_list(student_answer) or []
    spairs = _normalize_pairs(student)
    if spairs is None:
        spairs = []
    cmap = {l: r for l, r in correct_pairs}
    smap = {l: r for l, r in spairs}
    correct = 0
    for l, r in correct_pairs:
        if l in smap and _norm_text(smap[l]) == _norm_text(r):
            correct += 1
    n = len(correct_pairs)
    ratio = correct / n if n else 0.0
    earned = round(float(points_possible) * ratio, 4)
    feedback = (
        "All pairs are correct."
        if ratio >= 1.0
        else f"{correct} of {n} pairs are correct."
    )
    model = "; ".join(f"{a} → {b}" for a, b in correct_pairs)
    return {
        "points_earned": earned,
        "points_possible": float(points_possible),
        "feedback": feedback,
        "correct_answer": model,
        "confidence": 1.0,
    }


def try_deterministic_grade(
    question_type: str,
    content: Dict[str, Any],
    student_answer: Any,
    points_possible: float,
) -> Optional[Dict[str, Any]]:
    """
    Return a grade dict (without question_id) or None if LLM / unknown should handle.
    """
    qt = (question_type or "").strip().lower()
    if qt == "multiple_choice":
        return _try_grade_multiple_choice(content, student_answer, points_possible)
    if qt == "true_false":
        return _try_grade_true_false(content, student_answer, points_possible)
    if qt == "short_answer":
        return _try_grade_short_answer(content, student_answer, points_possible)
    if qt == "fill_blank":
        return _try_grade_fill_blank(content, student_answer, points_possible)
    if qt == "ordering":
        return _try_grade_ordering(content, student_answer, points_possible)
    if qt == "matching":
        return _try_grade_matching(content, student_answer, points_possible)
    return None


def _coerce_content(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _build_llm_question_payload(q: Dict[str, Any], content: Dict[str, Any]) -> Dict[str, Any]:
    """Shape expected by GeminiGrader.grade_questions_batch."""
    qtype = (q.get("question_type") or "").strip().lower()
    text = q.get("question_text") or ""
    student = q.get("student_answer", "")
    if qtype == "code":
        lang = content.get("language") or "unspecified"
        instructions = content.get("instructions") or ""
        starter = content.get("starter_code") or ""
        text = (
            f"[Code question — language: {lang}]\n{text}\n"
            f"[Starter code / context]\n{starter}\n"
            f"[Instructions for the learner]\n{instructions}\n"
        )
        if isinstance(student, str):
            sa = student
        else:
            sa = json.dumps(student, indent=2) if student is not None else ""
    elif isinstance(student, (dict, list)):
        sa = json.dumps(student, indent=2)
    else:
        sa = student if student is not None else ""

    payload: Dict[str, Any] = {
        "question_id": q.get("question_id"),
        "question_text": text,
        "question_type": qtype or "short_answer",
        "student_answer": sa,
        "points_possible": int(q.get("points_possible") or 0),
        "explanation": q.get("explanation"),
        "rubric": q.get("rubric") or content.get("rubric"),
    }
    return {k: v for k, v in payload.items() if v is not None}


def run_assessment_hybrid_grading(
    questions_data: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Grade assessment questions: deterministic first, then one LLM batch for the rest.

    Returns the same keys as GeminiGrader.grade_questions_batch.
    """
    from teacher.ai_grading_helper import ASSESSMENT_GRADING_TEMPLATE
    from ai.gemini_grader import GeminiGrader

    slot_count = len(questions_data)
    deterministic_slots: List[Optional[Dict[str, Any]]] = [None] * slot_count
    llm_indices: List[int] = []
    llm_queue: List[Dict[str, Any]] = []

    for idx, q in enumerate(questions_data):
        qid = q.get("question_id")
        if not qid:
            logger.warning("Assessment grading: missing question_id at index %s", idx)
            qid = f"missing-{idx}"
        qid = str(qid)
        qtype = (q.get("question_type") or "").strip().lower()
        content = _coerce_content(q.get("content"))
        points = float(q.get("points_possible") or 0)
        student = q.get("student_answer")

        det: Optional[Dict[str, Any]] = None
        if qtype in (
            "multiple_choice",
            "true_false",
            "short_answer",
            "fill_blank",
            "ordering",
            "matching",
        ):
            det = try_deterministic_grade(qtype, content, student, points)

        if det is not None:
            row = dict(det)
            row["question_id"] = qid
            deterministic_slots[idx] = row
        else:
            llm_indices.append(idx)
            llm_queue.append(_build_llm_question_payload(q, content))

    llm_results: List[Dict[str, Any]] = []
    if llm_queue:
        grader = GeminiGrader(prompt_template_name=ASSESSMENT_GRADING_TEMPLATE)
        batch = grader.grade_questions_batch(questions=llm_queue, assignment_context=context)
        llm_results = list(batch.get("grades") or [])

    if len(llm_results) != len(llm_indices):
        logger.warning(
            "Assessment LLM batch size mismatch: expected %s, got %s",
            len(llm_indices),
            len(llm_results),
        )

    llm_by_index: Dict[int, Dict[str, Any]] = {}
    for i, grade in enumerate(llm_results):
        if i < len(llm_indices):
            llm_by_index[llm_indices[i]] = grade

    grades_out: List[Dict[str, Any]] = []
    total_score = 0.0
    total_possible = 0.0

    for idx, q in enumerate(questions_data):
        qid = q.get("question_id")
        if not qid:
            qid = f"missing-{idx}"
        qid = str(qid)
        points_possible = float(q.get("points_possible") or 0)
        total_possible += points_possible

        if idx < len(deterministic_slots) and deterministic_slots[idx] is not None:
            g = dict(deterministic_slots[idx])
        elif idx in llm_by_index:
            g = dict(llm_by_index[idx])
        else:
            g = {
                "question_id": qid,
                "points_earned": 0.0,
                "points_possible": points_possible,
                "feedback": "Could not grade this question automatically. Please grade manually.",
                "correct_answer": "",
                "confidence": 0.0,
            }
        if "points_possible" not in g:
            g["points_possible"] = points_possible
        total_score += float(g.get("points_earned") or 0)
        grades_out.append(g)

    return {
        "grades": grades_out,
        "total_score": total_score,
        "total_possible": total_possible,
    }
