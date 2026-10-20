# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (Contact : odoo@cybrosys.com)
#
#    This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU AFFERO GENERAL PUBLIC LICENSE for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import logging
from markupsafe import escape

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class Webhook(http.Controller):
    """Cloud API webhook: GET verifica token, POST recibe mensajes."""

    def _get_verify_token(self):
        return (
            request.env["ir.config_parameter"].sudo().get_param(
                "all_in_one_whatsapp_integration.webhook_verify_token",
                default="")
            or "").strip()

    @http.route('/whatsapp_message', type='http', auth='public',
                methods=['GET'], csrf=False)
    def verify_webhook(self, **kwargs):
        mode = kwargs.get('hub.mode')
        token = kwargs.get('hub.verify_token')
        challenge = kwargs.get('hub.challenge')
        expected = self._get_verify_token()
        if mode == 'subscribe' and challenge and expected \
                and token == expected:
            return challenge
        _logger.warning("WhatsApp webhook verification failed")
        return request.make_response("Forbidden", status=403)

    @http.route('/whatsapp_message', type='json', auth='public',
                methods=['POST'], csrf=False)
    def receive_webhook(self):
        try:
            data = request.get_json_data() or {}
        except Exception as e:
            _logger.warning("WhatsApp webhook bad JSON: %s", e)
            return {"ok": False}
        try:
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    self._handle_change(change.get('value', {}) or {})
        except Exception as e:  # noqa: BLE001 - webhook never 500s Meta
            _logger.exception("WhatsApp webhook error: %s", e)
        # Siempre 200 para que Meta no reintente en bucle.
        return {"ok": True}

    def _handle_change(self, value):
        # Ignora receipts/statuses sin mensajes entrantes.
        messages = value.get('messages') or []
        contacts = value.get('contacts') or []
        if not messages or not contacts:
            return
        metadata = value.get('metadata') or {}
        business_number = str(
            metadata.get('display_phone_number') or "").strip()
        profile = (contacts[0].get('profile') or {}).get('name') or "WhatsApp"
        wa_id = str(contacts[0].get('wa_id') or "").strip()
        if not wa_id:
            return
        for msg in messages:
            text = ((msg.get('text') or {}).get('body') or "").strip()
            if not text:
                continue
            self._post_to_channel(
                business_number, profile, wa_id, text)

    def _post_to_channel(self, business_number, profile, wa_id, text):
        Partner = request.env['res.partner'].sudo()
        Channel = request.env['discuss.channel'].sudo()
        # Nunca crear res.users: solo res.partner.
        contact = Partner.search(
            ['|', ('phone', '=', wa_id), ('mobile', '=', wa_id)], limit=1)
        if not contact:
            contact = Partner.create({
                'name': profile[:100],
                'phone': wa_id,
                'mobile': wa_id,
                'comment': 'Created from WhatsApp webhook',
            })
        channel = Channel.search([('phone', '=', wa_id)], limit=1)
        if not channel:
            channel = Channel.create({
                'name': "%s (%s)" % (profile[:60], wa_id),
                'channel_type': 'livechat',
                'phone': wa_id,
            })
            try:
                channel.add_members(
                    partner_ids=contact.ids, invite=False)
            except Exception:
                _logger.debug("Could not add member to channel",
                              exc_info=True)
        channel.with_context(mail_create_nosubscribe=True).message_post(
            author_id=contact.id,
            body="<p>%s</p>" % escape(text[:4000]),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
