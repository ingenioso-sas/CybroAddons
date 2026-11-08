# -*- coding: utf-8 -*-
"""Normaliza datos existentes para la versión 19.0.1.0.2.

- Asigna compañía a proveedores y registros de cola existentes.
- Completa el tipo de mensaje de los registros antiguos.
- Normaliza teléfonos aptos a E.164 y libera ``next_attempt`` para que los
  pendientes se reintenten en el próximo ciclo.
"""
import logging

from odoo import api

from odoo.addons.all_in_one_whatsapp_integration.models import whatsapp_tools as tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, 1, {})
    company = env.company

    providers = env["whatsapp.provider"].sudo().with_context(
        active_test=False).search([("company_id", "=", False)])
    if providers:
        providers.write({"company_id": company.id})

    from odoo.addons.all_in_one_whatsapp_integration.models.whatsapp_provider \
        import _sync_provider_flags
    for current_company in env["res.company"].search([]):
        company_env = api.Environment(
            cr, 1, dict(env.context,
                        allowed_company_ids=[current_company.id]))
        _sync_provider_flags(
            company_env, inherit_old=(current_company == company))

    queue = env["whatsapp.queue.message"].sudo().search([])
    for record in queue:
        vals = {}
        if not record.company_id:
            vals["company_id"] = record.provider_id.company_id.id \
                or company.id
        if not record.message_type:
            if record.template_name:
                vals["message_type"] = "template"
            elif record.attachment_ids:
                vals["message_type"] = "document"
            else:
                vals["message_type"] = "text"
        normalized = tools.normalize_inbound_phone(record.phone) \
            or tools.normalize_e164(record.phone)
        if normalized and tools.is_valid_e164(normalized) \
                and normalized != record.phone:
            vals["phone"] = normalized
        if record.next_attempt:
            vals["next_attempt"] = False
        if vals:
            try:
                record.write(vals)
            except Exception as e:  # noqa: BLE001 - no abortar la migración
                _logger.warning(
                    "WhatsApp queue: no se pudo normalizar id=%s: %s",
                    record.id, e)
