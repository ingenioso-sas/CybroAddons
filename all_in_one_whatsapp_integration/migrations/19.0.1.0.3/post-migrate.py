# -*- coding: utf-8 -*-
"""Elimina referencias obsoletas a ``whatsapp_business`` en vistas.

El campo se retiró del modelo ``res.config.settings``. Si una base conserva
una vista antigua (por una actualización parcial o una personalización), el
cliente web falla con:

    "res.config.settings"."whatsapp_business" field is undefined

Esta migración limpia el label y el field de cualquier vista de ajustes.
"""
import logging
import re

from odoo import api

_logger = logging.getLogger(__name__)

_LABEL_RE = re.compile(
    r"<label[^>]*for=\"whatsapp_business\"[^>]*/>\s*", re.DOTALL)
_FIELD_RE = re.compile(
    r"<field[^>]*name=\"whatsapp_business\"[^>]*/>\s*", re.DOTALL)


def _clean_arch(arch):
    if not arch or "whatsapp_business" not in arch:
        return arch
    cleaned = _LABEL_RE.sub("", arch)
    cleaned = _FIELD_RE.sub("", cleaned)
    return cleaned


def migrate(cr, version):
    env = api.Environment(cr, 1, {})
    views = env["ir.ui.view"].sudo().search([
        ("model", "=", "res.config.settings"),
    ])
    for view in views:
        try:
            arch = view.arch
        except Exception:  # noqa: BLE001 - vista corrupta/heredada
            continue
        cleaned = _clean_arch(arch)
        if cleaned != arch:
            view.write({"arch": cleaned})
            _logger.info(
                "WhatsApp: limpiada referencia whatsapp_business en vista %s",
                view.id)
