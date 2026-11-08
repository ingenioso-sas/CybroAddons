# -*- coding: utf-8 -*-
###############################################################################
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    License AGPL-3. See LICENSE file for full copyright and licensing details.
###############################################################################
import json
import logging

from markupsafe import Markup, escape

from odoo import http
from odoo.http import request

from odoo.addons.all_in_one_whatsapp_integration.models import whatsapp_tools as tools

_logger = logging.getLogger(__name__)


class Webhook(http.Controller):
    """Cloud API webhook: GET verifica token, POST recibe mensajes."""

    def _get_param(self, key, default=False):
        return request.env["ir.config_parameter"].sudo().get_param(
            key, default)

    def _get_verify_token(self):
        return (self._get_param(
            "all_in_one_whatsapp_integration.webhook_verify_token", "")
            or "").strip()

    def _get_app_secret(self):
        return (self._get_param(
            "all_in_one_whatsapp_integration.whatsapp_app_secret", "")
            or "").strip()

    def _get_phone_number_id(self):
        value = (self._get_param(
            "all_in_one_whatsapp_integration.whatsapp_no", "")
            or "").strip()
        if value:
            return value
        provider = request.env["whatsapp.provider"].sudo().search(
            [("code", "=", "cloud"), ("active", "=", True)], limit=1)
        if provider:
            return (provider.sudo().cloud_phone_number_id or "").strip()
        return ""

    def _get_inbox_group(self):
        group_id = self._get_param(
            "all_in_one_whatsapp_integration.whatsapp_inbox_group_id")
        try:
            group_id = int(group_id or 0)
        except (TypeError, ValueError):
            group_id = 0
        group = request.env["res.groups"].sudo().browse(group_id).exists()
        if group:
            return group
        return request.env.ref("base.group_user", raise_if_not_found=False)

    def _verify_signature(self, raw_body):
        secret = self._get_app_secret()
        if not secret:
            _logger.error(
                "WhatsApp webhook: whatsapp_app_secret is not configured; "
                "rejecting POST. Configure the Meta App Secret in settings.")
            return False
        signature = request.httprequest.headers.get("X-Hub-Signature-256", "")
        valid = tools.verify_webhook_signature(secret, raw_body, signature)
        if not valid:
            _logger.warning("WhatsApp webhook: invalid signature")
        return valid

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

    @http.route('/whatsapp_message', type='http', auth='public',
                methods=['POST'], csrf=False)
    def receive_webhook(self, **kwargs):
        raw_body = request.httprequest.get_data()
        if not self._verify_signature(raw_body):
            return request.make_json_response(
                {"ok": False, "error": "invalid signature"}, status=403)
        try:
            data = json.loads(raw_body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError) as e:
            _logger.warning("WhatsApp webhook bad JSON: %s", e)
            return request.make_json_response(
                {"ok": False, "error": "invalid json"}, status=400)
        try:
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    self._handle_change(change.get('value', {}) or {})
        except Exception as e:  # noqa: BLE001 - Meta reintenta si hay 5xx
            _logger.exception("WhatsApp webhook error: %s", e)
            return request.make_json_response(
                {"ok": False, "error": "internal error"}, status=500)
        return request.make_json_response({"ok": True})

    def _handle_change(self, value):
        messages = value.get('messages') or []
        contacts = value.get('contacts') or []
        if not messages or not contacts:
            return
        metadata = value.get('metadata') or {}
        expected_phone_id = self._get_phone_number_id()
        phone_id = str(metadata.get('phone_number_id') or "").strip()
        if expected_phone_id and phone_id and phone_id != expected_phone_id:
            _logger.warning(
                "WhatsApp webhook: phone_number_id %s does not match the "
                "configured %s; ignoring payload.", phone_id,
                expected_phone_id)
            return
        business_number = str(
            metadata.get('display_phone_number') or "").strip()
        profile = (contacts[0].get('profile') or {}).get('name') or "WhatsApp"
        wa_id = str(contacts[0].get('wa_id') or "").strip()
        phone = tools.normalize_inbound_phone(wa_id)
        if not phone:
            _logger.warning(
                "WhatsApp webhook: invalid wa_id %r; ignoring payload.",
                wa_id)
            return
        for msg in messages:
            wamid = str(msg.get('id') or "").strip()
            if wamid and request.env['mail.message'].sudo().search_count(
                    [('whatsapp_message_id', '=', wamid)]):
                _logger.info("WhatsApp webhook: duplicate message %s", wamid)
                continue
            text = self._extract_text(msg)
            if not text:
                continue
            try:
                message = self._post_to_channel(
                    business_number, profile, phone, text)
                if message and wamid:
                    message.sudo().write({'whatsapp_message_id': wamid})
            except Exception as e:  # noqa: BLE001 - un mensaje no bloquea al resto
                _logger.exception(
                    "WhatsApp webhook: could not post message %s: %s",
                    wamid, e)

    @staticmethod
    def _extract_text(msg):
        text = ((msg.get('text') or {}).get('body') or "").strip()
        if text:
            return text
        button = msg.get('button') or {}
        if button.get('text'):
            return str(button['text']).strip()
        interactive = msg.get('interactive') or {}
        for key in ('button_reply', 'list_reply'):
            reply = interactive.get(key) or {}
            if reply.get('title'):
                return str(reply['title']).strip()
        for media in ('image', 'video', 'document', 'audio'):
            caption = (msg.get(media) or {}).get('caption')
            if caption:
                return str(caption).strip()
        msg_type = msg.get('type')
        if msg_type:
            return "[%s recibido]" % msg_type
        return ""

    def _post_to_channel(self, business_number, profile, phone, text):
        Partner = request.env['res.partner'].sudo()
        Channel = request.env['discuss.channel'].sudo()
        variants = tools.phone_search_variants(phone) or [phone]
        contact = Partner.search([('phone', 'in', variants)], limit=1)
        if not contact:
            contact = Partner.create({
                'name': profile[:100],
                'phone': phone,
                'comment': 'Created from WhatsApp webhook',
            })
        channel = Channel.search([('phone', 'in', variants)], limit=1)
        group = self._get_inbox_group()
        if not channel:
            vals = {
                'name': "%s (%s)" % (profile[:60], phone),
                'channel_type': 'channel',
                'phone': phone,
            }
            if group:
                vals['group_public_id'] = group.id
            channel = Channel.create(vals)
            try:
                channel.add_members(
                    partner_ids=contact.ids, post_joined_message=False)
            except Exception:
                _logger.debug("Could not add member to channel",
                              exc_info=True)
        elif channel.channel_type != 'channel' and group:
            # Canales creados por versiones anteriores (grupo privado):
            # agregar a los usuarios del grupo para que puedan verlos.
            try:
                partners = group.users.mapped('partner_id')
                if partners:
                    channel.add_members(
                        partner_ids=partners.ids, post_joined_message=False)
            except Exception:
                _logger.debug("Could not add group members to channel",
                              exc_info=True)
        body = Markup("<p>%s</p>") % escape(text[:4000])
        _logger.debug("WhatsApp inbound from %s (%s)", phone, business_number)
        return channel.with_context(
            whatsapp_inbound=True,
            mail_create_nosubscribe=True,
        ).message_post(
            author_id=contact.id,
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
