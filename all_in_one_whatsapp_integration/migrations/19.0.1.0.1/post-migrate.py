# -*- coding: utf-8 -*-
"""Reencola mensajes atascados en Error por el bug de reintentos.

Antes, el primer fallo pasaba el mensaje a ``error`` y el cron (que solo
busca ``pending``) nunca lo reintentaba. Ahora ``error`` solo se alcanza al
agotar el tope de reintentos, por lo que los registros heredados con
``retry_count`` por debajo del tope vuelven a ``pending`` para reintentarse
automáticamente cuando el proveedor esté disponible.
"""
import logging

from odoo import api

_logger = logging.getLogger(__name__)

PARAM_MAX_RETRIES = (
    "all_in_one_whatsapp_integration.whatsapp_queue_max_retries"
)


def migrate(cr, version):
    env = api.Environment(cr, 1, {})
    raw_max = env["ir.config_parameter"].sudo().get_param(
        PARAM_MAX_RETRIES, 5)
    try:
        max_retries = int(raw_max)
    except (TypeError, ValueError):
        max_retries = 5
    stuck = env["whatsapp.queue.message"].search([
        ("state", "=", "error"),
        ("retry_count", "<", max_retries),
    ])
    if stuck:
        stuck.write({"state": "pending", "retry_count": 0})
        _logger.info(
            "WhatsApp queue: %s mensajes en error reencolados.", len(stuck))
