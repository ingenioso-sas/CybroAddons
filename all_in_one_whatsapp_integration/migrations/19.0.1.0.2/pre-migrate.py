# -*- coding: utf-8 -*-
"""Limpieza de artefactos del modelo legacy ``whatsapp.message``.

Se ejecuta antes de cargar los datos del módulo. Usa ``raise_if_not_found``
para no generar trazas cuando el registro ya no existe (instalación nueva).
"""
from odoo import api

LEGACY_XMLIDS = [
    "all_in_one_whatsapp_integration.ir_cron_whatsapp_message_process",
    "all_in_one_whatsapp_integration.whatsapp_messages_menu",
    "all_in_one_whatsapp_integration.whatsapp_messages_technical_menu",
    "all_in_one_whatsapp_integration.whatsapp_message_action",
    "all_in_one_whatsapp_integration.whatsapp_message_tree_view",
    "all_in_one_whatsapp_integration.whatsapp_message_form_view",
    "all_in_one_whatsapp_integration.access_whatsapp_message",
]


def migrate(cr, version):
    env = api.Environment(cr, 1, {})
    # El proveedor ahora es único por (code, company_id), no por code.
    cr.execute("SELECT to_regclass('whatsapp_provider')")
    if cr.fetchone()[0]:
        cr.execute(
            "ALTER TABLE whatsapp_provider "
            "DROP CONSTRAINT IF EXISTS whatsapp_provider_code_uniq")
    for xmlid in LEGACY_XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            try:
                record.unlink()
            except Exception:  # noqa: BLE001 - la migración no debe abortar
                # Si otro registro depende de él, se deja para revisión manual.
                pass
