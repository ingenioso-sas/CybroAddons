# -*- coding: utf-8 -*-
"""Pure phone helpers (no Odoo dependency) + shared WhatsApp helpers.

Separar la parte pura permite testearla sin instancia de Odoo.
"""
import hashlib
import hmac
import re

_E164_RE = re.compile(r"^\+\d{7,15}$")
_NON_DIGIT_PLUS_RE = re.compile(r"[^\d+]")


def clean_number_digits(number):
    """Return digits-only number for Evolution API (no '+', no spaces)."""
    if number is None:
        return ""
    if not isinstance(number, str):
        number = str(number)
    return re.sub(r"\D", "", number)


def normalize_e164(number):
    """Return a cleaned phone number, optionally prefixed with '+'."""
    if number is None:
        return ""
    if not isinstance(number, str):
        number = str(number)
    cleaned = _NON_DIGIT_PLUS_RE.sub("", number.strip())
    if cleaned.startswith("+"):
        # Keep only the first '+' and drop any other plus signs.
        cleaned = "+" + cleaned[1:].replace("+", "")
    else:
        cleaned = cleaned.replace("+", "")
    return cleaned


def normalize_inbound_phone(number):
    """Normalize a Meta/Evolution inbound id (digits) to E.164 with '+'.

    Meta sends ``wa_id`` as digits without the leading plus (for example
    ``573001234567``). Returns ``'+573001234567'`` when valid, otherwise
    an empty string.
    """
    digits = clean_number_digits(number)
    if not digits:
        return ""
    candidate = "+" + digits
    return candidate if _E164_RE.match(candidate) else ""


def phone_search_variants(number):
    """Return the E.164 and digits-only spellings of a phone number."""
    normalized = normalize_inbound_phone(number)
    if not normalized:
        normalized = normalize_e164(number)
    if not normalized:
        return []
    digits = clean_number_digits(normalized)
    return list(dict.fromkeys([normalized, digits]))


def is_valid_e164(number):
    return bool(number and _E164_RE.match(normalize_e164(number)))


def validate_e164_or_raise(number, field_label="mobile"):
    """Raise ValueError (pure) — la capa Odoo lo convierte a ValidationError."""
    normalized = normalize_e164(number)
    if not normalized:
        raise ValueError("Add whatsapp mobile number in %s!" % field_label)
    if not is_valid_e164(normalized):
        raise ValueError(
            "Please add a valid mobile number along with "
            "a valid country code (E.164, e.g. +573001234567)!"
        )
    return normalized


def compute_webhook_signature(app_secret, raw_body):
    """Return the Meta ``X-Hub-Signature-256`` value for a raw body."""
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    digest = hmac.new(
        (app_secret or "").encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return "sha256=%s" % digest


def verify_webhook_signature(app_secret, raw_body, signature):
    """Constant-time verification of Meta's webhook signature."""
    if not app_secret or not signature:
        return False
    expected = compute_webhook_signature(app_secret, raw_body)
    return hmac.compare_digest(expected, signature)
