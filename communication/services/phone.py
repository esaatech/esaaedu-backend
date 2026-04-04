"""Phone normalization for SMS (E.164-style)."""


def normalize_to_e164(phone: str, default_country_code: str = "1") -> str:
    """
    Best-effort E.164 without extra dependencies.
    Strips non-digits except leading +; 10-digit US numbers get +1.
    """
    if not phone or not str(phone).strip():
        raise ValueError("Phone number is empty")

    raw = str(phone).strip()
    digits_only = "".join(c for c in raw if c.isdigit())

    if raw.startswith("+"):
        if not digits_only:
            raise ValueError("Invalid phone number")
        return f"+{digits_only}"

    if not digits_only:
        raise ValueError("Invalid phone number")

    if len(digits_only) == 10:
        return f"+{default_country_code}{digits_only}"
    if len(digits_only) == 11 and digits_only.startswith(default_country_code):
        return f"+{digits_only}"

    return f"+{digits_only}"


def phone_match_candidates(phone: str) -> frozenset[str]:
    """
    Possible string forms for the same line (+1 vs 1, spacing) for DB/thread matching.
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
