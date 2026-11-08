# -*- coding: utf-8 -*-
"""Proveedores de envío WhatsApp.

Un registro por canal (Web / Twilio / Cloud API / Evolution API).
El flag `active` es la ÚNICA fuente de verdad sobre qué proveedores
pueden usarse: el wizard solo ofrece los activos (dominio) y la cola
solo procesa los activos. Las credenciales pueden definirse por
proveedor (y por compañía) o seguir usando los parámetros globales
antiguos en ``ir.config_parameter``.
"""
import base64
import json
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import whatsapp_tools as tools
from .whatsapp_exceptions import WhatsappPermanentError

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

MANAGER_GROUP = "all_in_one_whatsapp_integration.group_whatsapp_manager"


def _sync_provider_flags(env, inherit_old=True):
    """Crea proveedores faltantes por compañía y hereda toggles antiguos."""
    ICP = env["ir.config_parameter"].sudo()
    Provider = env["whatsapp.provider"].sudo().with_context(
        active_test=False)
    for vals in PROVIDER_DATA:
        provider = Provider.search([
            ("code", "=", vals["code"]),
            ("company_id", "=", env.company.id),
        ], limit=1)
        if not provider:
            provider = Provider.create(dict(
                vals, active=(vals["code"] == "web"),
                company_id=env.company.id))
        old_key = OLD_PARAM_BY_CODE.get(vals["code"])
        if inherit_old and old_key and ICP.get_param(old_key):
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
    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, index=True,
        default=lambda self: self.env.company)

    # Credenciales por proveedor/compañía. Si están vacías se usan los
    # parámetros globales históricos de ir.config_parameter.
    cloud_bearer_token = fields.Char(
        string="Cloud: Access Token", groups=MANAGER_GROUP)
    cloud_phone_number_id = fields.Char(
        string="Cloud: Phone Number ID", groups=MANAGER_GROUP)
    cloud_graph_version = fields.Char(
        string="Cloud: Graph API Version", default="v27.0",
        groups=MANAGER_GROUP,
        help="Versión de Graph API, por ejemplo v27.0.")
    evolution_base_url = fields.Char(
        string="Evolution: URL base", groups=MANAGER_GROUP)
    evolution_instance = fields.Char(
        string="Evolution: Instancia", groups=MANAGER_GROUP)
    evolution_apikey = fields.Char(
        string="Evolution: apiKey", groups=MANAGER_GROUP)
    twilio_account_sid = fields.Char(
        string="Twilio: Account SID", groups=MANAGER_GROUP)
    twilio_auth_token = fields.Char(
        string="Twilio: Auth Token", groups=MANAGER_GROUP)
    twilio_whatsapp_number = fields.Char(
        string="Twilio: WhatsApp Number", groups=MANAGER_GROUP)

    last_test_state = fields.Selection(
        [("ok", "OK"), ("error", "Error")], string="Última prueba",
        readonly=True)
    last_test_date = fields.Datetime(string="Fecha última prueba",
                                     readonly=True)
    last_test_info = fields.Text(string="Detalle última prueba",
                                 readonly=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "Ya existe un proveedor con ese código en la compañía.")

    # ------------------------------------------------------------------
    # Helpers de credenciales
    # ------------------------------------------------------------------
    def _get_param(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def _get_credential(self, field_name, param_key, default=False):
        """Devuelve la credencial del proveedor o el parámetro global."""
        value = self.sudo()[field_name]
        if value:
            return value.strip() if isinstance(value, str) else value
        global_value = self._get_param(param_key, default)
        return global_value.strip() if isinstance(global_value, str) \
            else (global_value or default)

    def _get_graph_version(self):
        version = self._get_credential(
            "cloud_graph_version",
            "all_in_one_whatsapp_integration.whatsapp_graph_version",
            "v27.0") or "v27.0"
        return version if version.startswith("v") else "v%s" % version

    def _attachment_url(self, attachment):
        """URL pública temporal (token de Odoo) para un adjunto."""
        attachment = attachment.sudo()
        if not attachment.access_token:
            attachment.generate_access_token()
        base_url = (self._get_param("web.base.url") or "").rstrip("/")
        if not base_url:
            raise WhatsappPermanentError(
                _("Configure web.base.url para poder enviar adjuntos por "
                  "WhatsApp."))
        if not base_url.startswith("https://"):
            _logger.warning(
                "WhatsApp document URL is not HTTPS (%s); Meta/Twilio may "
                "not be able to download the attachment.", base_url)
        return "%s/web/content/%s?download=true&access_token=%s" % (
            base_url, attachment.id, attachment.access_token or "")

    @staticmethod
    def _extract_message_id(response):
        """Extrae el id del mensaje del proveedor cuando esté disponible."""
        if response is None:
            return False
        if hasattr(response, "sid"):  # Twilio
            return str(response.sid) if response.sid else False
        try:
            data = response.json()
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(data, dict):
            return False
        messages = data.get("messages")
        if isinstance(messages, list) and messages:
            return str(messages[0].get("id") or "") or False
        key = data.get("key")
        if isinstance(key, dict) and key.get("id"):
            return str(key["id"])
        return str(data.get("id") or "") or False

    @staticmethod
    def _parse_template_components(template_components):
        if not template_components:
            return []
        if isinstance(template_components, dict):
            return [template_components]
        if isinstance(template_components, list):
            return template_components
        try:
            parsed = json.loads(template_components)
        except (TypeError, ValueError) as e:
            raise WhatsappPermanentError(
                _("Componentes de plantilla inválidos: %s") % e)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise WhatsappPermanentError(
                _("Los componentes de la plantilla deben ser JSON de tipo "
                  "lista u objeto."))
        return parsed

    # ------------------------------------------------------------------
    # Envío (usado por la cola y por el wizard en modo directo)
    # ------------------------------------------------------------------
    @api.model
    def get_default_for_company(self, company, code=None):
        """Return the provider that should be used by default.

        When ``code`` is given, only that provider code is considered. When
        it is omitted, queue-capable providers are preferred, then Twilio,
        then WhatsApp Web.
        """
        company = company or self.env.company
        domain = [
            ("company_id", "=", company.id),
            ("active", "=", True),
        ]
        if code:
            domain.append(("code", "=", code))
            return self.sudo().search(domain, order="sequence, id", limit=1)
        providers = self.sudo().search(domain, order="sequence, id")
        for codes in (
            ("cloud", "evolution"),
            ("twilio",),
            ("web",),
        ):
            match = providers.filtered(lambda provider: provider.code in codes)
            if match:
                return match[:1]
        return providers[:1]

    def send_message(self, phone, body, attachment_ids=None,
                     message_type="text", template_name=False,
                     template_language="es", template_components=False):
        """Envía por este proveedor. Devuelve la respuesta del proveedor.

        Lanza ``WhatsappPermanentError`` para fallos 4xx no recuperables y
        ``UserError``/``ValidationError`` para el resto.
        """
        self.ensure_one()
        if not self.active:
            raise WhatsappPermanentError(
                _("El proveedor '%s' está deshabilitado. Actívelo en "
                  "WhatsApp → Proveedores (o en Ajustes → WhatsApp → "
                  "Canales habilitados).") % self.name)
        attachments = attachment_ids or self.env["ir.attachment"]
        if self.code == "cloud":
            return self._send_cloud(
                phone, body or "", attachments, message_type,
                template_name, template_language, template_components)
        if self.code == "evolution":
            return self._send_evolution(
                phone, body or "", attachments, message_type,
                template_name)
        if self.code == "twilio":
            return self._send_twilio(phone, body or "", attachments)
        raise WhatsappPermanentError(
            _("El proveedor '%s' es de envío directo y no usa la cola.")
            % self.name)

    def _check_http(self, response, provider_label):
        if 200 <= response.status_code < 300:
            return response
        text = response.text[:500]
        _logger.error("%s error %s: %s", provider_label,
                      response.status_code, text)
        message = _("%s error %s: %s") % (
            provider_label, response.status_code, text)
        if 400 <= response.status_code < 500 \
                and response.status_code not in (408, 429):
            raise WhatsappPermanentError(message)
        raise UserError(message)

    def _post_cloud(self, payload):
        bearer = self._get_credential(
            "cloud_bearer_token",
            "all_in_one_whatsapp_integration.bearer_token")
        wa_no = self._get_credential(
            "cloud_phone_number_id",
            "all_in_one_whatsapp_integration.whatsapp_no")
        if not bearer or not wa_no:
            raise WhatsappPermanentError(
                _("Configure Cloud API (token y phone number ID)."))
        url = "https://graph.facebook.com/%s/%s/messages" % (
            self._get_graph_version(), wa_no)
        try:
            response = requests.post(
                url, json=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer %s" % bearer},
                timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            raise UserError(_("No se pudo contactar Cloud API: %s") % e)
        return self._check_http(response, "Cloud API")

    def _send_cloud(self, phone, body, attachments, message_type="text",
                    template_name=False, template_language="es",
                    template_components=False):
        number = tools.normalize_e164(phone)
        if not tools.is_valid_e164(number):
            raise WhatsappPermanentError(
                _("Número de WhatsApp inválido: %s") % phone)
        if message_type == "template" or template_name:
            if not template_name:
                raise WhatsappPermanentError(
                    _("Indique el nombre de la plantilla de WhatsApp."))
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": template_language or "es"},
                    "components": self._parse_template_components(
                        template_components),
                },
            }
            return self._post_cloud(payload)
        if attachments:
            response = None
            for index, attachment in enumerate(attachments):
                attachment = attachment.sudo()
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": number,
                    "type": "document",
                    "document": {
                        "link": self._attachment_url(attachment),
                        "caption": body[:1024] if index == 0 else "",
                        "filename": attachment.name or "document.pdf",
                    },
                }
                response = self._post_cloud(payload)
            return response
        if len(body) > 4096:
            raise WhatsappPermanentError(
                _("El mensaje supera el límite de 4096 caracteres de "
                  "WhatsApp."))
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        return self._post_cloud(payload)

    def _send_evolution(self, phone, body, attachments, message_type="text",
                        template_name=False):
        from odoo.addons.all_in_one_whatsapp_integration.wizard \
            .whatsapp_mode_message import WhatsappModeMessage
        if message_type == "template" or template_name:
            raise WhatsappPermanentError(
                _("Evolution API no soporta plantillas de WhatsApp en este "
                  "módulo. Use Cloud API o un mensaje de texto."))
        if len(body) > 4096:
            raise WhatsappPermanentError(
                _("El mensaje supera el límite de 4096 caracteres de "
                  "WhatsApp."))
        helper = WhatsappModeMessage(self.env, provider=self)
        if not attachments:
            return helper.action_send_custom_message(phone, body)
        response = None
        for index, attachment in enumerate(attachments):
            attachment = attachment.sudo()
            try:
                raw = base64.b64decode(attachment.datas or b"")
            except Exception as e:
                raise WhatsappPermanentError(
                    _("Adjunto inválido: %s") % e)
            fname = attachment.name or "document.pdf"
            if "." not in fname:
                fname += ".pdf"
            response = helper.action_send_attachment_document_message(
                phone, fname, body if index == 0 else "",
                base64.b64encode(raw).decode("utf-8"))
        return response

    # -- envío Twilio (directo) ------------------------------------------
    def _send_twilio(self, phone, body, attachments=None):
        account_sid = self._get_credential(
            "twilio_account_sid",
            "all_in_one_whatsapp_integration.account_sid")
        auth_token = self._get_credential(
            "twilio_auth_token",
            "all_in_one_whatsapp_integration.auth_token")
        twilio_no = self._get_credential(
            "twilio_whatsapp_number",
            "all_in_one_whatsapp_integration.twilio_whatsapp")
        if not account_sid or not auth_token or not twilio_no:
            raise WhatsappPermanentError(
                _("Configure Twilio SID/token/number en Ajustes."))
        number = tools.normalize_e164(phone)
        if not tools.is_valid_e164(number):
            raise WhatsappPermanentError(
                _("Número de WhatsApp inválido: %s") % phone)
        media_urls = [self._attachment_url(a) for a in (attachments or [])]
        kwargs = {
            "from_": "whatsapp:" + twilio_no,
            "body": body or "",
            "to": "whatsapp:" + number.replace(" ", ""),
        }
        if media_urls:
            kwargs["media_url"] = media_urls
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            return client.messages.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            _logger.exception("Twilio send failed")
            status = getattr(e, "status", None)
            if isinstance(status, int) and 400 <= status < 500 \
                    and status not in (408, 429):
                raise WhatsappPermanentError(
                    _("Twilio send failed: %s") % e)
            raise UserError(_("Twilio send failed: %s") % e)

    # -- prueba de conexión ----------------------------------------------
    def run_test(self, phone):
        """Envía mensaje de prueba y audita el resultado en el proveedor."""
        self.ensure_one()
        try:
            number = tools.validate_e164_or_raise(phone or "", "prueba")
        except ValueError as e:
            raise ValidationError(str(e))
        body = "✅ Conexión WhatsApp OK (%s)" % self.name
        try:
            if self.code == "twilio":
                if not self.active:
                    raise WhatsappPermanentError(
                        _("El proveedor '%s' está deshabilitado. Actívelo en "
                          "WhatsApp → Proveedores (o en Ajustes → WhatsApp → "
                          "Canales habilitados).") % self.name)
                self._send_twilio(number, body)
            elif self.code in ("cloud", "evolution"):
                self.send_message(number, body)
            else:
                raise ValidationError(
                    _("Web no requiere prueba: abre WhatsApp Web."))
        except Exception as e:  # noqa: BLE001 - se audita y se relanza
            _logger.warning("WhatsApp provider test failed (%s): %s",
                            self.code, e)
            self.write({"last_test_state": "error",
                        "last_test_date": fields.Datetime.now(),
                        "last_test_info": str(e)[:2000]})
            raise
        self.write({"last_test_state": "ok",
                    "last_test_date": fields.Datetime.now(),
                    "last_test_info": _("Prueba enviada a %s.") % number})
        return True
