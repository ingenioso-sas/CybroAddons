import logging
import mimetypes

import requests

from odoo.exceptions import ValidationError
from odoo import _

from odoo.addons.all_in_one_whatsapp_integration.models import whatsapp_tools as tools
from odoo.addons.all_in_one_whatsapp_integration.models.whatsapp_exceptions \
    import WhatsappPermanentError

_logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 30

# Verificado en vivo contra Evolution 2.3.7 (2026-10-22):
#  sendText         -> {number, text, options, textMessage?}
#  sendMedia        -> {number, mediatype, mimetype, caption, media, fileName}
#  sendSticker      -> {number, sticker}
#  sendWhatsAppAudio-> {number, audio}


class WhatsappModeMessage:
    """Helper (no es un modelo Odoo) para Evolution API v2."""

    def __init__(self, env, provider=None):
        self.env = env
        self.provider = provider
        get = self.env['ir.config_parameter'].sudo().get_param
        if provider:
            self.evolution_base_url = (
                provider._get_credential(
                    'evolution_base_url',
                    'all_in_one_whatsapp_integration.evolution_base_url')
                or "").strip().rstrip("/")
            self.evolution_instance = (
                provider._get_credential(
                    'evolution_instance',
                    'all_in_one_whatsapp_integration.evolution_instance')
                or "").strip()
            self.evolution_apikey = (
                provider._get_credential(
                    'evolution_apikey',
                    'all_in_one_whatsapp_integration.evolution_apikey')
                or "").strip()
        else:
            self.evolution_base_url = (
                get('all_in_one_whatsapp_integration.evolution_base_url') or ""
            ).strip().rstrip("/")
            self.evolution_instance = (
                get('all_in_one_whatsapp_integration.evolution_instance') or ""
            ).strip()
            self.evolution_apikey = (
                get('all_in_one_whatsapp_integration.evolution_apikey') or ""
            ).strip()

    def clean_number(self, number):
        return tools.clean_number_digits(number)

    def _ensure_config(self):
        if not self.evolution_base_url or not self.evolution_instance \
                or not self.evolution_apikey:
            raise WhatsappPermanentError(
                _("Configure Evolution API (base URL, instance and apiKey) "
                  "in Settings before sending."))

    def build_URL(self, type_msg):
        self._ensure_config()
        return "%s/message/%s/%s" % (
            self.evolution_base_url, type_msg, self.evolution_instance)

    def build_payload_whatsapp(self, number, extra_options=None,
                               extra_sections=None):
        base_options = {"delay": 1200, "presence": "composing"}
        if extra_options:
            base_options.update(extra_options)
        payload = {"number": number, "options": base_options}
        if extra_sections:
            payload.update(extra_sections)
        return payload

    def send_request_whatsapp(self, url, payload):
        headers = {"Content-Type": "application/json",
                   "apikey": self.evolution_apikey}
        try:
            response = requests.post(url, json=payload, headers=headers,
                                     timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            _logger.exception("Error al conectar con Evolution API: %s", e)
            raise ValidationError(
                _("No se pudo contactar Evolution API: %s") % e)
        if response.status_code not in (200, 201):
            _logger.error("Evolution API error: %s %s",
                          response.status_code, response.text[:500])
            if response.status_code >= 500 \
                    and "connection closed" in response.text.lower():
                raise ValidationError(_(
                    "Evolution API perdió la conexión con WhatsApp en la "
                    "instancia '%s'. Reconecte la instancia (QR) en Evolution "
                    "Manager y reintente. Detalle: %s")
                    % (self.evolution_instance, response.text[:300]))
            message = _("Evolution API error %s: %s") % (
                response.status_code, response.text[:500])
            if 400 <= response.status_code < 500 \
                    and response.status_code not in (408, 429):
                raise WhatsappPermanentError(message)
            raise ValidationError(message)
        _logger.info("Mensaje WhatsApp enviado correctamente")
        return response

    @staticmethod
    def _guess_mimetype(file_name):
        guessed, _enc = mimetypes.guess_type(file_name or "")
        return guessed or "application/octet-stream"

    # -- texto -----------------------------------------------------------
    def action_send_custom_message(self, number, whatsapp_message):
        number = self.clean_number(number)
        url = self.build_URL("sendText")
        text = whatsapp_message or ""
        payload = self.build_payload_whatsapp(
            number, {"linkPreview": False},
            {"text": text, "textMessage": {"text": text}})
        return self.send_request_whatsapp(url, payload)

    # -- media (imagen / video / documento) ------------------------------
    def _send_media(self, number, mediatype, mimetype, caption, media,
                    file_name=None):
        url = self.build_URL("sendMedia")
        payload = {
            "number": self.clean_number(number),
            "mediatype": mediatype,
            "mimetype": mimetype or "application/octet-stream",
            "caption": caption or "",
            "media": str(media or ""),
        }
        if file_name:
            payload["fileName"] = file_name
        else:
            payload["delay"] = 1200
        return self.send_request_whatsapp(url, payload)

    # -- documento -------------------------------------------------------
    def action_send_attachment_document_message(self, number, file_name,
                                                whatsapp_message,
                                                message_type_media):
        """Documento: base64 o URL pública (ej. invoice.pdf)."""
        return self._send_media(
            number, "document", self._guess_mimetype(file_name or ""),
            whatsapp_message, message_type_media, file_name or "document.pdf")
