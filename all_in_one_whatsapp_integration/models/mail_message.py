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
import http.client
import json
import logging

import html2text

from odoo import api, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """Mirror discuss.channel messages to WhatsApp via Facebook Graph API."""
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, values_list):
        ICP = self.env['ir.config_parameter'].sudo()
        bearer_token = ICP.get_param(
            'all_in_one_whatsapp_integration.bearer_token')
        whatsapp_no = ICP.get_param(
            'all_in_one_whatsapp_integration.whatsapp_no')
        cloud_enabled = ICP.get_param(
            'all_in_one_whatsapp_integration.cloud_api_enabled')
        records = super().create(values_list)
        if not (bearer_token and whatsapp_no and cloud_enabled):
            return records
        for values, record in zip(values_list, records):
            try:
                if values.get('model') != 'discuss.channel' \
                        or not values.get('res_id'):
                    continue
                channel = self.env['discuss.channel'].browse(
                    values['res_id']).exists()
                if not channel or not channel.phone:
                    continue
                body_html = values.get('body') or ""
                try:
                    body = html2text.html2text(body_html).strip()[:4000]
                except Exception:
                    body = body_html[:4000]
                if not body:
                    continue
                conn = http.client.HTTPSConnection(
                    "graph.facebook.com", timeout=15)
                try:
                    payload = json.dumps({
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": channel.phone,
                        "type": "text",
                        "text": {"preview_url": False, "body": body},
                    })
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer %s' % bearer_token,
                    }
                    conn.request("POST",
                                 "/v17.0/%s/messages" % whatsapp_no,
                                 payload, headers)
                    resp = conn.getresponse()
                    resp.read()
                    if resp.status not in (200, 201):
                        _logger.warning(
                            "WhatsApp mirror failed ch=%s status=%s",
                            channel.id, resp.status)
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception as e:  # noqa: BLE001 - never break chatter
                _logger.exception("WhatsApp mirror error: %s", e)
        return records
