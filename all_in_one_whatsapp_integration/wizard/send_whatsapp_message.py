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
import urllib.parse as parse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class SendWhatsappMessage(models.TransientModel):
    """Wizard: envío directo o entrada real a la cola única.

    El proveedor es Many2one con dominio active: solo habilitados.
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

    @api.model
    def _default_provider(self):
        Provider = self.env['whatsapp.provider'].sudo().with_context(
            active_test=False)
        return (Provider.search([('code', '=', 'web'), ('active', '=', True)],
                                limit=1)
                or Provider.search([('active', '=', True)], limit=1)
                or Provider.search([], limit=1))

    sale_user_id = fields.Many2one(
        'res.partner', string="Partner Name", default=_default_partner,
        help="Select the partner associated with the sale.")
    whatsapp_mobile_number = fields.Char(
        related='sale_user_id.phone', readonly=True,
        help="The phone number associated with the selected partner.")
    whatsapp_message = fields.Text(
        string="WhatsApp Message",
        help="Enter the message to be sent via WhatsApp.")
    provider_id = fields.Many2one(
        'whatsapp.provider', string="Proveedor", required=True,
        domain=[('active', '=', True)], default=_default_provider,
        help="Solo se listan los proveedores habilitados en Ajustes.")
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

    def _get_provider(self):
        """Devuelve el proveedor elegido, garantizado habilitado."""
        provider = self.provider_id.sudo().with_context(
            active_test=False).exists()
        if not provider:
            raise ValidationError(_("Seleccione un proveedor."))
        if not provider.active:
            raise ValidationError(
                _("El proveedor '%s' está deshabilitado en Ajustes.")
                % provider.name)
        return provider

    def _get_number_e164(self):
        number = (self.sale_user_id.phone or "").strip()
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
        provider = self._get_provider()

        if self.delivery == 'queue':
            return self._enqueue(number, provider)
        if provider.code == 'twilio':
            return self._send_twilio(number, provider)
        if provider.code == 'web':
            return self._send_web(number)
        if provider.code in ('cloud', 'evolution'):
            provider.send_message(
                number, self.whatsapp_message or "", self.attachment_ids)
            return self._notify_sent(provider.name)
        raise ValidationError(_("Proveedor no soportado."))

    def _enqueue(self, number, provider):
        """Crea el registro en la cola única (solo cloud/evolution)."""
        if provider.code not in ('cloud', 'evolution'):
            raise ValidationError(
                _("Solo Cloud API y Evolution API usan la cola. "
                  "Web y Twilio son de envío directo."))
        queue = self.env['whatsapp.queue.message'].sudo()
        queue.create_queue_message(
            phone=number, message=self.whatsapp_message or "",
            provider_code=provider.code,
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
    def _send_twilio(self, number, provider):
        return provider._send_twilio(number, self.whatsapp_message or "")

    def _send_web(self, number):
        digits = number.replace(" ", "").replace("+", "")
        message_string = parse.quote((self.whatsapp_message or "").strip())
        link = "https://web.whatsapp.com/send?phone=" + digits
        if message_string:
            link += "&text=" + message_string
        return {'type': 'ir.actions.act_url', 'url': link,
                'target': 'new', 'res_id': self.id}
