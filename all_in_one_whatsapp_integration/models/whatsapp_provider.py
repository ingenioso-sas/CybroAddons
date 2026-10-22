# -*- coding: utf-8 -*-
"""Proveedores de envío WhatsApp.

Un registro por canal (Web / Twilio / Cloud API / Evolution API).
El flag `active` es la ÚNICA fuente de verdad sobre qué proveedores
pueden usarse: el wizard solo ofrece los activos (dominio) y la cola
solo procesa los activos. Las credenciales siguen en Ajustes
(ir.config_parameter) agrupadas por proveedor.
"""
from odoo import fields, models


class WhatsappProvider(models.Model):
    _name = "whatsapp.provider"
    _description = "Proveedor de envío WhatsApp"
    _order = "sequence, name"

    code = fields.Selection(
        [("web", "WhatsApp Web"),
         ("twilio", "Twilio"),
         ("cloud", "Cloud API (Meta)"),
         ("evolution", "Evolution API")],
        string="Código", required=True, index=True,
        help="Canal de envío. No cambiar una vez creado.")
    name = fields.Char(string="Nombre", required=True, translate=True)
    active = fields.Boolean(
        string="Habilitado", default=True, index=True,
        help="Solo los proveedores habilitados aparecen en el wizard "
             "y son procesados por la cola.")
    sequence = fields.Integer(string="Secuencia", default=10)

    last_test_state = fields.Selection(
        [("ok", "OK"), ("error", "Error")], string="Última prueba",
        readonly=True)
    last_test_date = fields.Datetime(string="Fecha última prueba",
                                     readonly=True)
    last_test_info = fields.Text(string="Detalle última prueba",
                                 readonly=True)

    _sql_constraints = [
        ("code_uniq", "UNIQUE(code)",
         "Ya existe un proveedor con ese código."),
    ]
