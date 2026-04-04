"""Resolve student_phone lines to profile display names for staff SMS inbox."""

from __future__ import annotations

from communication.services.phone import normalize_to_e164, phone_match_candidates


def _user_display(user) -> str:
    name = (user.get_full_name() or "").strip()
    if name:
        return name
    return (user.email or "").strip() or "Unknown"


def _child_label(sp) -> str:
    n = f"{sp.child_first_name or ''} {sp.child_last_name or ''}".strip()
    if n:
        return n
    return _user_display(sp.user)


def _register(norm_map: dict[str, str], raw_phone: str, label: str) -> None:
    """First normalized key wins (deterministic order of profile iteration)."""
    raw = (raw_phone or "").strip()
    if not raw:
        return
    try:
        canon = normalize_to_e164(raw)
    except ValueError:
        return
    if canon not in norm_map:
        norm_map[canon] = label


def build_student_phone_norm_to_label() -> dict[str, str]:
    """
    Map canonical E.164 to a short display name from Student/Parent/Teacher profiles.
    Collisions: first profile seen wins (query iteration order).
    """
    from users.models import ParentProfile, StudentProfile, TeacherProfile

    norm_map: dict[str, str] = {}

    for sp in StudentProfile.objects.select_related("user").iterator(chunk_size=500):
        if (sp.child_phone or "").strip():
            _register(norm_map, sp.child_phone, _child_label(sp))
        if (sp.parent_phone or "").strip():
            pl = (sp.parent_name or "").strip() or _user_display(sp.user)
            _register(norm_map, sp.parent_phone, pl)

    for pp in ParentProfile.objects.select_related("user").iterator(chunk_size=500):
        if (pp.phone_number or "").strip():
            _register(norm_map, pp.phone_number, _user_display(pp.user))

    for tp in TeacherProfile.objects.select_related("user").iterator(chunk_size=500):
        if (tp.phone_number or "").strip():
            _register(norm_map, tp.phone_number, _user_display(tp.user))

    return norm_map


def lookup_display_name(student_phone: str, norm_to_label: dict[str, str]) -> str:
    for c in phone_match_candidates(student_phone):
        try:
            key = normalize_to_e164(c)
            if key in norm_to_label:
                return norm_to_label[key]
        except ValueError:
            continue
    # Fallback: last 10 digits vs profile keys (handles odd formatting mismatches).
    digits_in = "".join(ch for ch in (student_phone or "") if ch.isdigit())
    if len(digits_in) >= 10:
        tail = digits_in[-10:]
        for canon, label in norm_to_label.items():
            cd = "".join(ch for ch in canon if ch.isdigit())
            if len(cd) >= 10 and cd[-10:] == tail:
                return label
    return ""


def enrich_rows_contact_display(
    rows: list[dict],
    *,
    phone_key: str = "student_phone",
    name_key: str = "contact_display_name",
    norm_to_label: dict[str, str] | None = None,
) -> None:
    """Mutate each row dict with name_key; reuse norm_to_label when batching."""
    if not rows:
        return
    norm = norm_to_label if norm_to_label is not None else build_student_phone_norm_to_label()
    for r in rows:
        phone = (r.get(phone_key) or "").strip()
        r[name_key] = lookup_display_name(phone, norm) if phone else ""
