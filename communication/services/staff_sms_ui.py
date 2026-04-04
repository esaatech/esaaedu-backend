"""Querysets and read semantics for the staff SMS inbox UI."""

from __future__ import annotations

from django.db.models import Count, Exists, Max, OuterRef, Q
from django.utils import timezone

from communication.models import SmsRoutingLog
from communication.services.phone import normalize_to_e164

# Latest-first window for staff thread panel (inbound + outbound).
SMS_THREAD_MESSAGE_LIMIT = 10

# Twilio terminal failure-ish statuses for staff “delivery issues” list.
# "canceled" can appear when a message is stopped before delivery.
DELIVERY_ISSUE_STATUSES = frozenset({"failed", "undelivered", "canceled"})


def _delivery_issue_status_q() -> Q:
    q = Q()
    for st in DELIVERY_ISSUE_STATUSES:
        q |= Q(delivery_status__iexact=st)
    return q

PhonePair = tuple[str, str]


def admin_queue_inbound_filter():
    """Inbound rows counted as Admin SMS (unread) on the admin dashboard."""
    return Q(direction=SmsRoutingLog.Direction.INBOUND) & (
        Q(inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN)
        | Q(inbound_routing=SmsRoutingLog.InboundRouting.PENDING)
        | Q(inbound_routing__isnull=True)
    )


def admin_queue_inbound_queryset():
    return SmsRoutingLog.objects.filter(admin_queue_inbound_filter())


def teacher_routed_unread_queryset():
    """Inbound routed SMS with no read_at (teacher-facing unread; staff inbox section)."""
    return SmsRoutingLog.objects.filter(
        direction=SmsRoutingLog.Direction.INBOUND,
        inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        read_at__isnull=True,
    )


def inbound_sms_in_admin_queue(log: SmsRoutingLog) -> bool:
    if log.direction != SmsRoutingLog.Direction.INBOUND:
        return False
    r = log.inbound_routing
    return r in (
        SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        SmsRoutingLog.InboundRouting.PENDING,
        None,
    )


def mark_admin_queue_inbound_read(pk) -> bool:
    """Used by Django admin change view: only admin-queue inbound."""
    log = (
        SmsRoutingLog.objects.filter(pk=pk)
        .only("direction", "inbound_routing", "read_at")
        .first()
    )
    if log is None or not inbound_sms_in_admin_queue(log) or log.read_at is not None:
        return False
    updated = SmsRoutingLog.objects.filter(pk=pk, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return updated > 0


def mark_inbound_read_for_staff_inbox(pk) -> bool:
    """
    Mark a single inbound log read (e.g. Django admin change view path).
    Prefer mark_all_conversation_inbound_read for the staff inbox thread open.
    """
    log = (
        SmsRoutingLog.objects.filter(pk=pk)
        .only("direction", "read_at")
        .first()
    )
    if log is None or log.direction != SmsRoutingLog.Direction.INBOUND or log.read_at is not None:
        return False
    updated = SmsRoutingLog.objects.filter(pk=pk, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return updated > 0


def phone_match_candidates(phone: str) -> frozenset[str]:
    """
    DB values for the same line sometimes differ slightly (+1 vs 1, spacing).
    Used so inbound/outbound rows still share one thread.
    """
    raw = (phone or "").strip()
    if not raw:
        return frozenset()
    cands: set[str] = {raw}
    try:
        cands.add(normalize_to_e164(raw))
    except ValueError:
        pass
    if raw.startswith("+"):
        tail = raw[1:].strip()
        if tail:
            cands.add(tail)
            try:
                cands.add(normalize_to_e164(tail))
            except ValueError:
                pass
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        try:
            cands.add(normalize_to_e164(digits))
        except ValueError:
            pass
    if len(digits) == 11 and digits.startswith("1"):
        try:
            cands.add(normalize_to_e164(digits))
        except ValueError:
            pass
    return frozenset(x for x in cands if x)


def conversation_match_q(anchor: SmsRoutingLog) -> Q:
    sp = phone_match_candidates(anchor.student_phone)
    tw = phone_match_candidates(anchor.twilio_number)
    return Q(student_phone__in=sp, twilio_number__in=tw)


def conversation_thread_for_anchor(
    anchor: SmsRoutingLog,
    *,
    limit: int = SMS_THREAD_MESSAGE_LIMIT,
) -> list[SmsRoutingLog]:
    """Chronological SMS history (oldest first) for the same line + counterparty."""
    q = conversation_match_q(anchor)
    rows = list(
        SmsRoutingLog.objects.filter(q).order_by("-created_at")[: max(1, min(limit, 50))]
    )
    rows.reverse()
    return rows


def mark_all_conversation_inbound_read(anchor: SmsRoutingLog) -> int:
    """When staff opens a thread, mark every unread inbound in this conversation read."""
    q = conversation_match_q(anchor)
    return SmsRoutingLog.objects.filter(
        q,
        direction=SmsRoutingLog.Direction.INBOUND,
        read_at__isnull=True,
    ).update(read_at=timezone.now())


def sms_capable_users_qs():
    """
    Students / parents / teachers who have at least one non-empty SMS number on profile.
    """
    from users.models import ParentProfile, StudentProfile, TeacherProfile, User

    stu_phones = Exists(
        StudentProfile.objects.filter(user_id=OuterRef("pk")).filter(
            (Q(child_phone__isnull=False) & ~Q(child_phone__exact=""))
            | (Q(parent_phone__isnull=False) & ~Q(parent_phone__exact=""))
        )
    )
    par_phones = Exists(
        ParentProfile.objects.filter(user_id=OuterRef("pk"))
        .exclude(phone_number__exact="")
        .exclude(phone_number__isnull=True)
    )
    tea_phones = Exists(
        TeacherProfile.objects.filter(user_id=OuterRef("pk"))
        .exclude(phone_number__exact="")
        .exclude(phone_number__isnull=True)
    )
    return User.objects.filter(
        Q(role=User.Role.STUDENT) & stu_phones
        | Q(role=User.Role.PARENT) & par_phones
        | Q(role=User.Role.TEACHER) & tea_phones
    )


def contacts_directory_flat_entries(*, search: str = "", limit: int = 500) -> list[dict]:
    """
    Flat rows for contact picker: one row per (user, phone line), sorted by display then phone.
    """
    from communication.services.staff_outbound import resolve_staff_compose_phones

    lim = max(1, min(int(limit), 600))
    qs = sms_capable_users_qs().order_by("first_name", "last_name", "email")
    s = (search or "").strip()
    if len(s) >= 1:
        qs = qs.filter(
            Q(email__icontains=s)
            | Q(first_name__icontains=s)
            | Q(last_name__icontains=s)
            | Q(public_handle__icontains=s)
        )
    entries: list[dict] = []
    max_users_scan = 800
    for u in qs[:max_users_scan]:
        display = (u.get_full_name() or "").strip() or (u.email or "")
        for p in resolve_staff_compose_phones(u):
            entries.append(
                {
                    "user_id": u.pk,
                    "display": display,
                    "email": u.email,
                    "role": u.role,
                    "phone": p["phone"],
                    "phone_key": p["key"],
                    "phone_label": p["label"],
                }
            )
            if len(entries) >= lim:
                break
        if len(entries) >= lim:
            break
    entries.sort(key=lambda x: (x["display"].lower(), x["phone"]))
    return entries[:lim]


def recent_outbound_delivery_preview(*, limit: int = 8) -> list[dict]:
    """
    Latest outbound rows with whatever delivery_status we have (for empty-state troubleshooting).
    """
    limit = max(1, min(int(limit), 20))
    rows = (
        SmsRoutingLog.objects.filter(direction=SmsRoutingLog.Direction.OUTBOUND)
        .order_by("-created_at")
        .values(
            "pk",
            "student_phone",
            "delivery_status",
            "delivery_error_code",
            "created_at",
            "twilio_message_sid",
        )[:limit]
    )
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "log_id": str(r["pk"]),
                "student_phone": r["student_phone"],
                "delivery_status": (r["delivery_status"] or "").strip() or None,
                "delivery_error_code": (r["delivery_error_code"] or "").strip() or None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "has_twilio_sid": bool(r["twilio_message_sid"]),
            }
        )
    return out


def delivery_issue_summaries(*, limit: int = 25) -> list[dict]:
    """Recent outbound SMS with failed or undelivered status (for admin follow-up)."""
    limit = max(1, min(int(limit), 100))
    qs = (
        SmsRoutingLog.objects.filter(
            direction=SmsRoutingLog.Direction.OUTBOUND,
        )
        .filter(_delivery_issue_status_q())
        .order_by("-delivery_updated_at", "-created_at")[:limit]
    )
    rows: list[dict] = []
    for log in qs:
        rows.append(
            {
                "default_log_id": str(log.pk),
                "student_phone": log.student_phone,
                "twilio_number": log.twilio_number,
                "created_at": log.created_at.isoformat(),
                "delivery_status": log.delivery_status,
                "delivery_error_code": log.delivery_error_code,
                "delivery_error_message": log.delivery_error_message,
                "delivery_updated_at": (
                    log.delivery_updated_at.isoformat() if log.delivery_updated_at else None
                ),
                "preview": (log.body or "")[:200],
            }
        )
    return rows


def log_to_list_item(log: SmsRoutingLog) -> dict:
    return {
        "id": str(log.pk),
        "created_at": log.created_at.isoformat(),
        "direction": log.direction,
        "inbound_routing": log.inbound_routing,
        "read_at": log.read_at.isoformat() if log.read_at else None,
        "student_phone": log.student_phone,
        "body_preview": (log.body or "")[:200],
        "teacher_id": log.teacher_id,
        "twilio_message_sid": log.twilio_message_sid,
    }


def phones_with_admin_queue_unread() -> set[PhonePair]:
    """Numbers that still have unread admin-queue inbound (excluded from teacher lists)."""
    rows = (
        admin_queue_inbound_queryset()
        .filter(read_at__isnull=True)
        .values("twilio_number", "student_phone")
        .distinct()
    )
    return {(r["twilio_number"], r["student_phone"]) for r in rows}


def _serialize_thread_row(
    *,
    twilio_number: str,
    student_phone: str,
    unread_count: int,
    last_at,
    default_log_id: str,
    preview_body: str,
) -> dict:
    return {
        "student_phone": student_phone,
        "twilio_number": twilio_number,
        "unread_count": unread_count,
        "has_unread": unread_count > 0,
        "last_activity_at": last_at.isoformat() if last_at else None,
        "preview": (preview_body or "")[:240],
        "default_log_id": default_log_id,
    }


def admin_queue_thread_summaries(*, recent_limit: int = 10) -> tuple[list[dict], list[dict]]:
    """
    One row per (twilio_number, student_phone) for admin-queue inbounds only.
    Returns (unread_threads, recent_threads_with_all_admin_read).
    """
    unread_threads: list[dict] = []
    order_keys: list[PhonePair] = []
    by_key: dict[PhonePair, dict] = {}

    unread_qs = admin_queue_inbound_queryset().filter(read_at__isnull=True).order_by("-created_at")
    for log in unread_qs.iterator(chunk_size=200):
        key = (log.twilio_number, log.student_phone)
        if key not in by_key:
            by_key[key] = {"count": 0, "default_log": log, "last_at": log.created_at}
            order_keys.append(key)
        by_key[key]["count"] += 1

    for key in order_keys:
        data = by_key[key]
        log = data["default_log"]
        unread_threads.append(
            _serialize_thread_row(
                twilio_number=key[0],
                student_phone=key[1],
                unread_count=data["count"],
                last_at=data["last_at"],
                default_log_id=str(log.pk),
                preview_body=log.body or "",
            )
        )

    recent_groups = (
        admin_queue_inbound_queryset()
        .values("twilio_number", "student_phone")
        .annotate(
            unread=Count("id", filter=Q(read_at__isnull=True)),
            last_at=Max("created_at"),
        )
        .filter(unread=0)
        .order_by("-last_at")[:recent_limit]
    )
    recent_threads: list[dict] = []
    for g in recent_groups:
        t, p = g["twilio_number"], g["student_phone"]
        log = (
            admin_queue_inbound_queryset()
            .filter(twilio_number=t, student_phone=p)
            .order_by("-created_at")
            .first()
        )
        if log:
            recent_threads.append(
                _serialize_thread_row(
                    twilio_number=t,
                    student_phone=p,
                    unread_count=0,
                    last_at=g["last_at"],
                    default_log_id=str(log.pk),
                    preview_body=log.body or "",
                )
            )

    return unread_threads, recent_threads


def teacher_routed_thread_summaries(
    *,
    admin_unread_phones: set[PhonePair],
    recent_offset: int = 0,
    recent_limit: int = 10,
) -> tuple[list[dict], list[dict], bool]:
    """
    Routed inbound threads. Excludes any (twilio, phone) that still has unread admin-queue inbound
    so each number appears in at most one section (admin takes priority).

    Returns (unread_threads, recent_page_threads, recent_has_more).
    """
    unread_order: list[PhonePair] = []
    unread_by_key: dict[PhonePair, dict] = {}

    routed_unread = teacher_routed_unread_queryset().order_by("-created_at")
    for log in routed_unread.iterator(chunk_size=200):
        key = (log.twilio_number, log.student_phone)
        if key in admin_unread_phones:
            continue
        if key not in unread_by_key:
            unread_by_key[key] = {"count": 0, "default_log": log, "last_at": log.created_at}
            unread_order.append(key)
        unread_by_key[key]["count"] += 1

    unread_threads: list[dict] = []
    for key in unread_order:
        data = unread_by_key[key]
        log = data["default_log"]
        unread_threads.append(
            _serialize_thread_row(
                twilio_number=key[0],
                student_phone=key[1],
                unread_count=data["count"],
                last_at=data["last_at"],
                default_log_id=str(log.pk),
                preview_body=log.body or "",
            )
        )

    routed_base = SmsRoutingLog.objects.filter(
        direction=SmsRoutingLog.Direction.INBOUND,
        inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
    )
    group_iter = (
        routed_base.values("twilio_number", "student_phone")
        .annotate(
            unread_routed=Count("id", filter=Q(read_at__isnull=True)),
            last_at=Max("created_at"),
        )
        .filter(unread_routed=0)
        .order_by("-last_at")
        .iterator(chunk_size=100)
    )

    skipped = 0
    raw_page: list[dict] = []
    need = recent_limit + 1
    for g in group_iter:
        key = (g["twilio_number"], g["student_phone"])
        if key in admin_unread_phones:
            continue
        if skipped < recent_offset:
            skipped += 1
            continue
        raw_page.append(g)
        if len(raw_page) >= need:
            break

    has_more = len(raw_page) > recent_limit
    raw_page = raw_page[:recent_limit]

    recent_list: list[dict] = []
    for g in raw_page:
        t, p = g["twilio_number"], g["student_phone"]
        log = (
            routed_base.filter(twilio_number=t, student_phone=p)
            .order_by("-created_at")
            .first()
        )
        if log:
            recent_list.append(
                _serialize_thread_row(
                    twilio_number=t,
                    student_phone=p,
                    unread_count=0,
                    last_at=g["last_at"],
                    default_log_id=str(log.pk),
                    preview_body=log.body or "",
                )
            )

    return unread_threads, recent_list, has_more
