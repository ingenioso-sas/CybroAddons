# -*- coding: utf-8 -*-
###############################################################################
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    License AGPL-3. See LICENSE file for full copyright and licensing details.
###############################################################################
import logging

import html2text

from odoo import api, fields, models

from . import whatsapp_tools as tools

_logger = logging.getLogger(__name__)

COMMENT_SUBTYPE = 'mail.mt_comment'
NOTE_SUBTYPE = 'mail.mt_note'


class MailMessage(models.Model):
    """Encola (no envía) mensajes de discuss.channel a WhatsApp.

    Solo espeja mensajes escritos por usuarios internos. Los mensajes
    entrantes del webhook se marcan con el contexto ``whatsapp_inbound``
    y nunca se reenvían (evita el eco). El envío real lo hace el cron de
    la cola única, donde el fallo queda registrado y es reintentable.
    """
    _inherit = 'mail.message'

    whatsapp_message_id = fields.Char(
        string='WhatsApp Message ID', index=True, copy=False,
        help="ID (wamid) del mensaje de WhatsApp; se usa para deduplicar "
             "webhooks.")
    _whatsapp_message_id_uniq = models.Constraint(
        "UNIQUE(whatsapp_message_id)",
        "El ID de mensaje de WhatsApp ya existe.")

    @api.model
    def _get_whatsapp_mirror_provider(self):
        return self.env['whatsapp.provider'].sudo().search(
            [('active', '=', True),
             ('code', 'in', ('cloud', 'evolution')),
             ('company_id', '=', self.env.company.id)],
            order='sequence, id', limit=1)

    @api.model
    def _whatsapp_mirror_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'all_in_one_whatsapp_integration.whatsapp_discuss_mirror', '1')
        return str(value).lower() in ('1', 'true', 'yes')

    @api.model
    def _should_mirror_message(self, record):
        if self.env.context.get('whatsapp_inbound'):
            return False
        if not record.model or record.model != 'discuss.channel':
            return False
        if not record.res_id or record.message_type != 'comment':
            return False
        note_subtype = self.env.ref(NOTE_SUBTYPE, raise_if_not_found=False)
        if note_subtype and record.subtype_id == note_subtype:
            return False
        # Solo mensajes escritos por usuarios internos, no por el contacto
        # ni por usuarios portal/públicos.
        internal_users = record.author_id.user_ids.filtered(
            lambda user: user.has_group('base.group_user'))
        if not internal_users:
            return False
        return True

    @api.model_create_multi
    def create(self, values_list):
        records = super().create(values_list)
        if not self._whatsapp_mirror_enabled():
            return records
        candidates = [
            record for record in records
            if record.model == 'discuss.channel' and record.res_id
        ]
        if not candidates:
            return records
        provider = self._get_whatsapp_mirror_provider()
        if not provider:
            return records
        Queue = self.env['whatsapp.queue.message'].sudo()
        for record in candidates:
            try:
                if not self._should_mirror_message(record):
                    continue
                channel = self.env['discuss.channel'].browse(
                    record.res_id).exists()
                if not channel or not channel.phone:
                    continue
                try:
                    body = html2text.html2text(
                        record.body or "").strip()[:4000]
                except Exception:
                    body = (record.body or "")[:4000]
                attachments = record.attachment_ids
                if not body and not attachments:
                    continue
                channel_phone = tools.normalize_inbound_phone(
                    channel.phone) or channel.phone
                contact = self.env['res.partner'].sudo().search(
                    [('phone', 'in',
                      tools.phone_search_variants(channel_phone) or
                      [channel_phone])], limit=1)
                Queue.create_queue_message(
                    phone=channel_phone,
                    message=body,
                    provider_code=provider.code,
                    partner_id=contact.id or False,
                    attachment_ids=attachments,
                    model=record.model,
                    res_id=record.res_id,
                    message_type='document' if attachments else 'text',
                    company_id=provider.company_id.id,
                )
            except Exception as e:  # noqa: BLE001 - nunca romper el chatter
                _logger.exception("WhatsApp mirror enqueue error: %s", e)
        return records
