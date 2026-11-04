# -*- coding: utf-8 -*-
"""Limpia el campo Idioma fijo de las plantillas WhatsApp (v17.0.4.0.0).

Un lang fijo como 'es' anula el idioma del partner y, al no existir
traducción 'es' (solo es_ES), el render cae al inglés. Con Idioma vacío
el mensaje sale en el idioma del cliente.
"""
from odoo import api

XMLIDS = [
    "all_in_one_whatsapp_integration.sale_order_whatsapp_template",
    "all_in_one_whatsapp_integration.purchase_order_whatsapp_template",
    "all_in_one_whatsapp_integration.account_move_whatsapp_template",
    "all_in_one_whatsapp_integration.stock_picking_whatsapp_template",
]


def migrate(cr, version):
    env = api.Environment(cr, 1, {})
    for xmlid in XMLIDS:
        try:
            template = env.ref(xmlid, raise_if_not_found=False)
        except Exception:
            continue
        if template and template.lang:
            template.sudo().write({"lang": False})
