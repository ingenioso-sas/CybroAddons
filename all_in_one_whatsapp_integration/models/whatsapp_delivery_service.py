# -*- coding: utf-8 -*-
# Copyright 2026 PayOnline Ing
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""High-level WhatsApp sending service.

Business modules should call this service instead of reimplementing phone
resolution, provider selection and queue/direct branching.
"""

import logging

from odoo import api, models

from . import whatsapp_tools as tools

_logger = logging.getLogger(__name__)


class WhatsappMessageService(models.AbstractModel):
    _name = "whatsapp.message.service"
    _description = "High-level WhatsApp message service"

    @api.model
    def send_to_partner(self, partner, body, company=None, **kwargs):
        """Send a message to the partner's WhatsApp recipient.

        Enforces consent and resolves the contact/commercial fallback.
        """
        recipient = partner._get_whatsapp_recipient()
        if not recipient._can_send_whatsapp():
            return self._result(
                False, "no_destination", recipient=recipient
            )
        result = self.send_to_number(
            recipient._get_whatsapp_number(),
            body,
            company=company or recipient.company_id,
            partner_id=recipient.id,
            **kwargs,
        )
        result["recipient"] = recipient
        return result

    @api.model
    def send_to_number(
        self,
        phone,
        body,
        company=None,
        partner_id=False,
        model=False,
        res_id=False,
        message_type="text",
        template_name=False,
        template_language="es",
        template_components=False,
        attachment_ids=False,
    ):
        """Send a message to a number using the default company provider."""
        normalized = tools.normalize_e164(phone)
        if not tools.is_valid_e164(normalized):
            return self._result(False, "no_destination", phone=phone)

        company = company or self.env.company
        provider = self.env["whatsapp.provider"].get_default_for_company(
            company
        )
        if not provider:
            return self._result(
                False, "no_provider", phone=normalized
            )

        base_values = {
            "provider": provider,
            "phone": normalized,
        }
        if provider.code in ("cloud", "evolution"):
            try:
                queue = (
                    self.env["whatsapp.queue.message"]
                    .sudo()
                    .create_queue_message(
                        phone=normalized,
                        message=body or "",
                        provider_code=provider.code,
                        partner_id=partner_id,
                        attachment_ids=attachment_ids,
                        model=model,
                        res_id=res_id,
                        message_type=message_type,
                        template_name=template_name,
                        template_language=template_language,
                        template_components=template_components,
                        company_id=company.id,
                    )
                )
            except Exception as error:  # noqa: BLE001
                _logger.exception(
                    "Unable to queue WhatsApp message for %s.", normalized
                )
                return self._result(
                    False,
                    "error",
                    error=str(error),
                    **base_values,
                )
            return self._result(
                True, "", queue=queue, **base_values
            )

        if provider.code == "twilio":
            try:
                response = provider.send_message(
                    normalized,
                    body or "",
                    attachment_ids,
                    message_type=message_type,
                )
            except Exception as error:  # noqa: BLE001
                _logger.exception(
                    "Unable to send WhatsApp message to %s.", normalized
                )
                return self._result(
                    False,
                    "error",
                    error=str(error),
                    **base_values,
                )
            return self._result(
                True, "", response=response, **base_values
            )

        if provider.code == "web":
            return self._result(
                False, "web_not_supported", **base_values
            )
        return self._result(
            False, "unsupported_provider", **base_values
        )

    @api.model
    def _result(self, sent, reason="", **kwargs):
        return {
            "sent": bool(sent),
            "reason": reason,
            "queue": False,
            "provider": self.env["whatsapp.provider"],
            "phone": "",
            "error": "",
            "recipient": self.env["res.partner"],
            **kwargs,
        }
