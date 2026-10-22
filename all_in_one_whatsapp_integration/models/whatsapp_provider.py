# -*- coding: utf-8 -*-
"""Proveedores de envío WhatsApp.

Un registro por canal (Web / Twilio / Cloud API / Evolution API).
El flag `active` es la ÚNICA fuente de verdad sobre qué proveedores
pueden usarse: el wizard solo ofrece los activos (dominio) y la cola
solo procesa los activos. Las credenciales siguen en Ajustes
(ir.config_parameter) agrupadas por proveedor.
"""
import base64
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 30

OLD_PARAM_BY_CODE = {
    "twilio": "all_in_one_whatsapp_integration.twilio_enabled",
    "cloud": "all_in_one_whatsapp_integration.cloud_api_enabled",
    "evolution": "all_in_one_whatsapp_integration.evolution_api_enabled",
}

PROVIDER_DATA = [
    {"code": "web", "name": "WhatsApp Web", "sequence": 10},
    {"code": "twilio", "name": "Twilio", "sequence": 20},
    {"code": "cloud", "name": "Cloud API (Meta)", "sequence": 30},
    {"code": "evolution", "name": "Evolution API", "sequence": 40},
]


def _sync_provider_flags(env):
    """Crea proveedores faltantes y hereda los toggles antiguos."""
    ICP = env["ir.config_parameter"].sudo()
    Provider = env["whatsapp.provider"].sudo().with_context(
        active_test=False)
    for vals in PROVIDER_DATA:
        provider = Provider.search([("code", "=", vals["code"])], limit=1)
        if not provider:
            provider = Provider.create(dict(vals, active=(vals["code"] == "web")))
        old_key = OLD_PARAM_BY_CODE.get(vals["code"])
        if old_key and ICP.get_param(old_key):
            provider.active = True


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

    # ------------------------------------------------------------------
    # Envío (usado por la cola y por el wizard en modo directo)
    # ------------------------------------------------------------------
    def _get_param(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def send_message(self, phone, body, attachment_ids=None):
        """Envía por este proveedor. Solo cloud/evolution (encolables).

        Web y Twilio son de envío directo y no pasan por la cola.
        Devuelve el objeto response de la API. Lanza UserError/ValidationError
        con la causa para que la cola la guarde en error_msg.
        """
        self.ensure_one()
        if not self.active:
            raise ValidationError(
                _("El proveedor '%s' está deshabilitado.") % self.name)
        attachments = attachment_ids or self.env["ir.attachment"]
        if self.code == "cloud":
            return self._send_cloud(phone, body or "", attachments)
        if self.code == "evolution":
            return self._send_evolution(phone, body or "", attachments)
        raise ValidationError(
            _("El proveedor '%s' es de envío directo y no usa la cola.")
            % self.name)

    def _check_http(self, response, provider_label):
        if response.status_code in (200, 201):
            return response
        _logger.error("%s error %s: %s", provider_label,
                      response.status_code, response.text[:500])
        raise UserError(_("%s error %s: %s") % (
            provider_label, response.status_code, response.text[:500]))

    def _send_cloud(self, phone, body, attachments):
        from . import whatsapp_tools as tools
        bearer = (self._get_param(
            "all_in_one_whatsapp_integration.bearer_token") or "").strip()
        wa_no = (self._get_param(
            "all_in_one_whatsapp_integration.whatsapp_no") or "").strip()
        if not bearer or not wa_no:
            raise ValidationError(
                _("Configure Cloud API (token y phone number ID)."))
        number = tools.normalize_e164(phone)
        if attachments:
            attachment = attachments[0].sudo()
            if not attachment.access_token:
                attachment.generate_access_token()
            base_url = (self._get_param("web.base.url") or "").rstrip("/")
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": number,
                "type": "document",
                "document": {
                    "link": "%s/web/content/%s?download=true&access_token=%s"
                            % (base_url, attachment.id,
                               attachment.access_token or ""),
                    "caption": body[:1024],
                    "filename": attachment.name or "document.pdf",
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": number,
                "type": "text",
                "text": {"preview_url": False, "body": body},
            }
        try:
            response = requests.post(
                "https://graph.facebook.com/v17.0/%s/messages" % wa_no,
                json=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer %s" % bearer},
                timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise UserError(_("No se pudo contactar Cloud API: %s") % e)
        return self._check_http(response, "Cloud API")

    def _send_evolution(self, phone, body, attachments):
        from odoo.addons.all_in_one_whatsapp_integration.wizard \
            .whatsapp_mode_message import WhatsappModeMessage
        helper = WhatsappModeMessage(self.env)
        if not attachments:
            return helper.action_send_custom_message(phone, body)
        attachment = attachments[0].sudo()
        try:
            raw = base64.b64decode(attachment.datas or b"")
        except Exception as e:
            raise ValidationError(_("Adjunto inválido: %s") % e)
        fname = attachment.name or "document.pdf"
        if "." not in fname:
            fname += ".pdf"
        return helper.action_send_attachment_document_message(
            phone, fname, body, base64.b64encode(raw).decode("utf-8"))
