import logging

import requests

from odoo.exceptions import ValidationError
from odoo import _

from odoo.addons.all_in_one_whatsapp_integration.models import whatsapp_tools as tools

_logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 30


class WhatsappModeMessage:
    """Helper (no es un modelo Odoo) para Evolution API."""

    def __init__(self, env):
        self.env = env
        get = self.env["ir.config_parameter"].sudo().get_param
        self.evolution_base_url = (
            get("all_in_one_whatsapp_integration.evolution_base_url") or ""
        ).strip().rstrip("/")
        self.evolution_instance = (
            get("all_in_one_whatsapp_integration.evolution_instance") or ""
        ).strip()
        self.evolution_apikey = (
            get("all_in_one_whatsapp_integration.evolution_apikey") or ""
        ).strip()

    def clean_number(self, number):
        return tools.clean_number_digits(number)

    def _ensure_config(self):
        if not self.evolution_base_url or not self.evolution_instance \
                or not self.evolution_apikey:
            raise ValidationError(
                _("Configure Evolution API (base URL, instance and apiKey) "
                  "in Settings before sending.")
            )

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

    def _base_media_payload(self, number, mediatype, caption, media,
                            extra_options=None, **extra_media):
        payload = self.build_payload_whatsapp(number, extra_options)
        media_msg = {"mediatype": mediatype, "caption": caption or "",
                     "media": str(media or "")}
        media_msg.update(extra_media)
        payload["mediaMessage"] = media_msg
        return payload

    def send_request_whatsapp(self, url, payload):
        headers = {"Content-Type": "application/json",
                   "apikey": self.evolution_apikey}
        try:
            response = requests.post(url, json=payload, headers=headers,
                                     timeout=REQUEST_TIMEOUT)
            if response.status_code in (200, 201):
                _logger.info("WhatsApp message sent via Evolution API")
            else:
                _logger.error("Evolution API error: %s %s",
                              response.status_code, response.text[:500])
            return response
        except requests.RequestException as e:
            _logger.exception("Error connecting to Evolution API: %s", e)
            raise ValidationError(
                _("Could not reach Evolution API: %s") % e)

    def action_send_custom_message(self, number, whatsapp_message):
        number = self.clean_number(number)
        url = self.build_URL("sendText")
        payload = self.build_payload_whatsapp(
            number, {"linkPreview": False},
            {"textMessage": {"text": whatsapp_message or ""}})
        return self.send_request_whatsapp(url, payload)

    def action_send_image_message(self, number, whatsapp_message,
                                  message_type_media):
        """Send image (base64 or public URL). Formats: jpg/jpeg/png."""
        number = self.clean_number(number)
        url = self.build_URL("sendMedia")
        payload = self._base_media_payload(
            number, "image", whatsapp_message, message_type_media)
        return self.send_request_whatsapp(url, payload)

    def action_send_video_message(self, number, whatsapp_message,
                                  message_type_media):
        """Send video (base64 or public URL). Format: mp4."""
        number = self.clean_number(number)
        url = self.build_URL("sendMedia")
        payload = self._base_media_payload(
            number, "video", whatsapp_message, message_type_media)
        return self.send_request_whatsapp(url, payload)

    def action_send_attachment_document_message(self, number, file_name,
                                                whatsapp_message,
                                                message_type_media):
        """Send document (base64 or public URL). e.g. invoice.pdf."""
        number = self.clean_number(number)
        url = self.build_URL("sendMedia")
        payload = self._base_media_payload(
            number, "document", whatsapp_message, message_type_media,
            fileName=file_name or "document.pdf")
        return self.send_request_whatsapp(url, payload)

    def action_send_sticker_message(self, number, message_type_media):
        """Send sticker: base64 .webp or public URL."""
        number = self.clean_number(number)
        url = self.build_URL("sendSticker")
        payload = self.build_payload_whatsapp(
            number, None,
            {"stickerMessage": {"image": str(message_type_media)}})
        return self.send_request_whatsapp(url, payload)

    def action_send_audio_message(self, number, message_type_media):
        """Send audio: base64 .mp3/.ogg or public URL."""
        number = self.clean_number(number)
        url = self.build_URL("sendWhatsAppAudio")
        payload = self.build_payload_whatsapp(
            number, {"delay": 1200, "presence": "recording",
                     "encoding": True},
            {"audioMessage": {"audio": str(message_type_media)}})
        return self.send_request_whatsapp(url, payload)
