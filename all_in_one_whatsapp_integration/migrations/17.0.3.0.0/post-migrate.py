# -*- coding: utf-8 -*-
"""Migración a cola única + proveedores (v17.0.3.0.0).

- Asegura los 4 proveedores y hereda los toggles antiguos
  (twilio/cloud/evolution_enabled) al flag active.
"""
from odoo import api


def migrate(cr, version):
    env = api.Environment(cr, 1, {})
    from odoo.addons.all_in_one_whatsapp_integration.models \
        .whatsapp_provider import _sync_provider_flags
    _sync_provider_flags(env)
