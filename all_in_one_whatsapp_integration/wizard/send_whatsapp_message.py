# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (Contact : odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import base64
import logging
import urllib.parse as parse

import requests
from twilio.rest import Client

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .whatsapp_mode_message import WhatsappModeMessage, REQUEST_TIMEOUT

_logger = logging.getLogger(__name__)

SEND_MODES = [
    ('web', 'WhatsApp Web'),
    ('twilio', 'Twilio'),
    ('cloud', 'Cloud WhatsApp'),
    ('evolution', 'Evolution WhatsApp'),
]


class SendWhatsappMessage(models.TransientModel):
    """Wizard to send a message via Web / Twilio / Cloud / Evolution."""
    _name = 'send.whatsapp.message'
    _description = "Helps to send messages using different way"

    @api.model
    def _default_partner(self):
        try:
            active_model = self._context.get('active_model')
            active_ids = self._context.get('active_ids') or []
            if not active_model or not active_ids:
                return False
            record = self.env[active_model].browse(active_ids[0]).exists()
            partner = getattr(record, 'partner_id', False)
            return partner.id if partner else False
        except Exception:
            return False

    sale_user_id = fields.Many2one(
        'res.partner', string="Partner Name", default=_default_partner,
        help="Select the partner associated with the sale.")
    whatsapp_mobile_number = fields.Char(
        related='sale_user_id.mobile', readonly=True,
        help="The mobile number associated with the selected partner.")
    whatsapp_message = fields.Text(
        string="WhatsApp Message",
        help="Enter the message to be sent via WhatsApp.")
    send_mode = fields.Selection(
        SEND_MODES, string="Send Using", default='web', required=True,
        help="Select the mode to send the WhatsApp message.")
    attachment_ids = fields.Many2many(
        'ir.attachment', 'send_whatsapp_message_attachment_rel', 'wizard_id',
        'attachment_id', string='Attachments',
        help="Attachments to include in the WhatsApp message.")
    message_type = fields.Selection(
        string='Message Type',
        selection=[('text', 'Text'), ('document', 'Document')],
        default='text')

    def _get_param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _ensure_mode_enabled(self):
        enabled_map = {
            'twilio': 'all_in_one_whatsapp_integration.twilio_enabled',
            'cloud': 'all_in_one_whatsapp_integration.cloud_api_enabled',
            'evolution':
                'all_in_one_whatsapp_integration.evolution_api_enabled',
        }
        key = enabled_map.get(self.send_mode)
        if key and not self._get_param(key):
            raise ValidationError(
                _("Mode '%s' is disabled in Settings.") % self.send_mode)

    def _get_number_e164(self):
        number = (self.sale_user_id.mobile or "").strip()
        if not number:
            raise ValidationError(
                _('Add whatsapp mobile number in sale order partner!'))
        compact = number.replace(" ", "")
        if not compact.startswith("+"):
            raise ValidationError(
                _('Please add a valid mobile number along with a valid '
                  'country code!'))
        return compact

    def _get_private_attachment_url(self, attachment):
        base_url = (
            self._get_param('web.base.url') or "").rstrip("/")
        attachment = attachment.sudo().exists()
        attachment.ensure_one()
        # No marcamos public=True (exponía facturas). Usamos token firmado.
        if not attachment.access_token:
            attachment.generate_access_token()
        token = attachment.access_token or ""
        return ("%s/web/content/%s?download=true&access_token=%s"
                % (base_url, attachment.id, token))

    def action_send_custom_message(self):
        """Dispatch to the selected provider. Validates everything first."""
        self.ensure_one()
        self._ensure_mode_enabled()
        number = self._get_number_e164()
        if not (self.whatsapp_message or "").strip() \
                and not self.attachment_ids:
            raise ValidationError(_("Write a message or attach a file."))

        if self.send_mode == 'twilio':
            return self._send_twilio(number)
        if self.send_mode == 'web':
            return self._send_web(number)
        if self.send_mode == 'cloud':
            return self._send_cloud(number)
        if self.send_mode == 'evolution':
            return self._send_evolution(number)
        raise ValidationError(_("Unknown send mode."))

    # -- providers -----------------------------------------------------
    def _send_twilio(self, number):
        account_sid = (self._get_param(
            'all_in_one_whatsapp_integration.account_sid') or "").strip()
        auth_token = (self._get_param(
            'all_in_one_whatsapp_integration.auth_token') or "").strip()
        twilio_whatsapp = (self._get_param(
            'all_in_one_whatsapp_integration.twilio_whatsapp') or "").strip()
        if not account_sid or not auth_token or not twilio_whatsapp:
            raise ValidationError(
                _("Configure Twilio SID/token/number in Settings."))
        try:
            client = Client(account_sid, auth_token)
            return client.messages.create(
                from_='whatsapp:' + twilio_whatsapp,
                body=self.whatsapp_message or "",
                to='whatsapp:' + number.replace(" ", ""),
            )
        except Exception as e:
            _logger.exception("Twilio send failed")
            raise UserError(_("Twilio send failed: %s") % e)

    def _send_web(self, number):
        digits = number.replace(" ", "").replace("+", "")
        message_string = parse.quote((self.whatsapp_message or "").strip())
        link = "https://web.whatsapp.com/send?phone=" + digits
        if message_string:
            link += "&text=" + message_string
        return {'type': 'ir.actions.act_url', 'url': link,
                'target': 'new', 'res_id': self.id}

    def _send_cloud(self, number):
        bearer_token = (self._get_param(
            'all_in_one_whatsapp_integration.bearer_token') or "").strip()
        whatsapp_no = (self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_no') or "").strip()
        if not bearer_token or not whatsapp_no:
            raise ValidationError(
                _("Configure Cloud API token and phone number ID."))
        if self.message_type == 'document':
            if not self.attachment_ids:
                raise ValidationError(
                    _("Attach a file to send a document via Cloud API."))
            attachment = self.attachment_ids[0]
            file_link = self._get_private_attachment_url(attachment)
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": number,
                "type": "document",
                "document": {
                    "link": file_link,
                    "caption": (self.whatsapp_message or "")[:1024],
                    "filename": attachment.name or "document.pdf",
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": number,
                "type": "text",
                "text": {"preview_url": False,
                         "body": self.whatsapp_message or ""},
            }
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Bearer %s' % bearer_token}
        try:
            response = requests.post(
                "https://graph.facebook.com/v17.0/%s/messages" % whatsapp_no,
                json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            _logger.exception("Cloud API connection error")
            raise UserError(_("Could not reach Cloud API: %s") % e)
        if response.status_code not in (200, 201):
            _logger.error("Cloud API error %s: %s", response.status_code,
                          response.text[:1000])
            raise UserError(
                _("Cloud API error %s: %s") % (
                    response.status_code, response.text[:500]))
        return response

    def _send_evolution(self, number):
        helper = WhatsappModeMessage(self.env)
        text = self.whatsapp_message or ""
        if not self.attachment_ids:
            return helper.action_send_custom_message(number, text)
        attachment = self.attachment_ids[0].sudo()
        try:
            raw = base64.b64decode(attachment.datas or b"")
        except Exception as e:
            raise ValidationError(_("Invalid attachment data: %s") % e)
        b64_clean = base64.b64encode(raw).decode('utf-8')
        fname = attachment.name or "document.pdf"
        if not fname.lower().endswith(".pdf") and "." not in fname:
            fname += ".pdf"
        return helper.action_send_attachment_document_message(
            number, fname, text, b64_clean)
