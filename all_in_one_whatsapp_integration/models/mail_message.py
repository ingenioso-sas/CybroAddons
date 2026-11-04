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

import html2text

from odoo import api, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """Encola (no envía) mensajes de discuss.channel a WhatsApp.

    El envío real lo hace el cron de la cola única, donde el fallo
    queda registrado con su causa y es reintentable.
    """
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, values_list):
        records = super().create(values_list)
        cloud = self.env['whatsapp.provider'].sudo().with_context(
            active_test=False).search([('code', '=', 'cloud')], limit=1)
        if not cloud or not cloud.active:
            return records
        Queue = self.env['whatsapp.queue.message'].sudo()
        for values in values_list:
            try:
                if values.get('model') != 'discuss.channel' \
                        or not values.get('res_id'):
                    continue
                channel = self.env['discuss.channel'].browse(
                    values['res_id']).exists()
                if not channel or not channel.phone:
                    continue
                try:
                    body = html2text.html2text(
                        values.get('body') or "").strip()[:4000]
                except Exception:
                    body = (values.get('body') or "")[:4000]
                if not body:
                    continue
                Queue.create_queue_message(
                    phone=channel.phone, message=body,
                    provider_code='cloud')
            except Exception as e:  # noqa: BLE001 - nunca romper el chatter
                _logger.exception("WhatsApp mirror enqueue error: %s", e)
        return records
