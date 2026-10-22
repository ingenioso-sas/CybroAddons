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
#    along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import logging
import urllib.parse as parse

from twilio.rest import Client

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SEND_MODES = [
    ('web', 'WhatsApp Web'),
    ('twilio', 'Twilio'),
    ('cloud', 'Cloud WhatsApp'),
    ('evolution', 'Evolution WhatsApp'),
]


class SendWhatsappMessage(models.TransientModel):
    """Wizard: envío directo o entrada real a la cola única.

    El proveedor se valida contra whatsapp.provider (solo habilitados).
    Cloud/Evolution envían vía provider.send_message (mismo código que la
    cola); Web/Twilio son de envío directo.
    """
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

    @api.model
    def _default_delivery(self):
        if self.env['ir.config_parameter'].sudo().get_param(
                'all_in_one_whatsapp_integration.whatsapp_async_default'):
            return 'queue'
        return 'now'

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
    delivery = fields.Selection(
        [('now', 'Enviar ahora'), ('queue', 'Encolar')],
        string="Entrega", default=_default_delivery, required=True,
        help="Encolar deja el mensaje en la cola única para que lo "
             "procese el cron (con reintentos y causa de fallo visible).")
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

    def _get_provider(self, code):
        provider = self.env['whatsapp.provider'].sudo().with_context(
            active_test=False).search([('code', '=', code)], limit=1)
        if not provider:
            raise ValidationError(
                _("Proveedor desconocido: %s") % code)
        if not provider.active:
            raise ValidationError(
                _("El proveedor '%s' está deshabilitado en Ajustes.")
                % provider.name)
        return provider

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

    def action_send_custom_message(self):
        """Envío directo o entrada real a la cola única."""
        self.ensure_one()
        number = self._get_number_e164()
        if not (self.whatsapp_message or "").strip() \
                and not self.attachment_ids:
            raise ValidationError(_("Write a message or attach a file."))

        if self.delivery == 'queue':
            return self._enqueue(number)
        if self.send_mode == 'twilio':
            return self._send_twilio(number)
        if self.send_mode == 'web':
            return self._send_web(number)
        if self.send_mode in ('cloud', 'evolution'):
            provider = self._get_provider(self.send_mode)
            provider.send_message(
                number, self.whatsapp_message or "", self.attachment_ids)
            return self._notify_sent(provider.name)
        raise ValidationError(_("Unknown send mode."))

    def _enqueue(self, number):
        """Crea el registro en la cola única (solo cloud/evolution)."""
        if self.send_mode not in ('cloud', 'evolution'):
            raise ValidationError(
                _("Solo Cloud API y Evolution API usan la cola. "
                  "Web y Twilio son de envío directo."))
        queue = self.env['whatsapp.queue.message'].sudo()
        queue.create_queue_message(
            phone=number, message=self.whatsapp_message or "",
            provider_code=self.send_mode,
            partner_id=self.sale_user_id.id or False,
            attachment_ids=self.attachment_ids,
            model=self._context.get('active_model'),
            res_id=(self._context.get('active_ids') or [False])[0] or False)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Encolado'),
                       'message': _('Mensaje en la cola de WhatsApp.'),
                       'type': 'success', 'sticky': False},
        }

    def _notify_sent(self, provider_name):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Enviado'),
                       'message': _('Mensaje enviado por %s.') % provider_name,
                       'type': 'success', 'sticky': False},
        }

    # -- envío directo (no encolables) -----------------------------------
    def _send_twilio(self, number):
        self._get_provider('twilio')
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
