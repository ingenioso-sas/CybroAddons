# -*- coding: utf-8 -*-
"""Pure phone helpers (no Odoo dependency) + shared Odoo service.

Separar la parte pura permite testearla sin instancia de Odoo.
"""
import logging
import re

_logger = logging.getLogger(__name__)

_E164_RE = re.compile(r"^\+\d{7,15}$")


def clean_number_digits(number):
    """Return digits-only number for Evolution API (no '+', no spaces)."""
    if number is None:
        return ""
    if not isinstance(number, str):
        number = str(number)
    return re.sub(r"\D", "", number)


def normalize_e164(number):
    """Return E.164 number ('+123...') or '' if not parseable."""
    if number is None:
        return ""
    if not isinstance(number, str):
        number = str(number)
    cleaned = number.strip().replace(" ", "").replace("-", "")
    cleaned = cleaned.replace("(", "").replace(")", "")
    if cleaned and not cleaned.startswith("+"):
        # Sin código país no podemos adivinarlo: se devuelve tal cual
        # para que la validación lo rechace con mensaje claro.
        return cleaned
    return cleaned


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
