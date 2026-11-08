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

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.all_in_one_whatsapp_integration.models import whatsapp_tools as tools
from odoo.addons.all_in_one_whatsapp_integration.models.whatsapp_exceptions \
    import WhatsappPermanentError

_logger = logging.getLogger(__name__)


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
            active_model = self.env.context.get('active_model')
            active_ids = self.env.context.get('active_ids') or []
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
        Provider = self.env['whatsapp.provider'].with_context(
            active_test=False)
        # Preferir canales que soportan adjuntos; Web es el último recurso.
        return (Provider.search([
                    ('code', 'in', ('cloud', 'evolution')),
                    ('active', '=', True)], limit=1, order='sequence, id')
                or Provider.search([('code', '=', 'web'),
                                    ('active', '=', True)], limit=1)
                or Provider.search([('active', '=', True)], limit=1)
                or Provider.search([], limit=1))

    sale_user_id = fields.Many2one(
        'res.partner', string="Partner Name", default=_default_partner,
        help="Select the partner associated with the sale.")
    whatsapp_mobile_number = fields.Char(
        string="Whatsapp Number", compute='_compute_whatsapp_mobile_number',
        help="The phone/mobile number associated with the selected partner.")
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
    warning_message = fields.Text(
        string='Aviso', readonly=True,
        help="Advertencias generadas al preparar el documento.")

    def _get_param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    @api.depends('sale_user_id.phone', 'sale_user_id.mobile')
    def _compute_whatsapp_mobile_number(self):
        for wizard in self:
            partner = wizard.sale_user_id
            wizard.whatsapp_mobile_number = (
                partner.phone or partner.mobile or "") if partner else ""

    def _get_provider(self):
        """Devuelve el proveedor elegido, garantizado habilitado."""
        provider = self.provider_id.sudo().with_context(
            active_test=False).exists()
        if not provider:
            raise ValidationError(_("Seleccione un proveedor."))
        if not provider.active:
            raise ValidationError(
                _("El proveedor '%s' está deshabilitado. Actívelo en "
                  "WhatsApp → Proveedores (o en Ajustes → WhatsApp → "
                  "Canales habilitados).") % provider.name)
        if provider.company_id and provider.company_id not in self.env.companies:
            raise ValidationError(
                _("El proveedor '%s' pertenece a otra compañía.")
                % provider.name)
        return provider

    def _get_number_e164(self):
        partner = self.sale_user_id
        number = (partner.phone or partner.mobile or "").strip() \
            if partner else ""
        try:
            return tools.validate_e164_or_raise(
                number, "sale order partner")
        except ValueError as e:
            raise ValidationError(_(str(e)))

    def action_send_custom_message(self):
        """Envío directo o entrada real a la cola única."""
        self.ensure_one()
        number = self._get_number_e164()
        if not (self.whatsapp_message or "").strip() \
                and not self.attachment_ids:
            raise ValidationError(_("Write a message or attach a file."))
        provider = self._get_provider()
        if provider.code == 'web' and self.attachment_ids:
            raise ValidationError(_(
                "WhatsApp Web no permite adjuntar archivos automáticamente. "
                "Quite los adjuntos o use Cloud API/Evolution API."))
        if self.delivery == 'queue':
            return self._enqueue(number, provider)
        if provider.code == 'twilio':
            return self._send_twilio(number, provider)
        if provider.code == 'web':
            return self._send_web(number)
        if provider.code in ('cloud', 'evolution'):
            return self._send_now_or_enqueue(number, provider)
        raise ValidationError(_("Proveedor no soportado."))

    def _create_queue_record(self, number, provider, error_msg=False):
        queue = self.env['whatsapp.queue.message'].sudo()
        record = queue.create_queue_message(
            phone=number, message=self.whatsapp_message or "",
            provider_code=provider.code,
            partner_id=self.sale_user_id.id or False,
            attachment_ids=self.attachment_ids,
            model=self.env.context.get('active_model'),
            res_id=(self.env.context.get('active_ids') or [False])[0] or False,
            message_type='document' if self.attachment_ids else 'text',
            company_id=provider.company_id.id)
        if error_msg:
            record.write({'error_msg': str(error_msg)[:2000]})
        return record

    def _enqueue(self, number, provider):
        """Crea el registro en la cola única (solo cloud/evolution)."""
        if provider.code not in ('cloud', 'evolution'):
            raise ValidationError(
                _("Solo Cloud API y Evolution API usan la cola. "
                  "Web y Twilio son de envío directo."))
        self._create_queue_record(number, provider)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Encolado'),
                       'message': _('Mensaje en la cola de WhatsApp.'),
                       'type': 'success', 'sticky': False},
        }

    def _send_now_or_enqueue(self, number, provider):
        """Envía ya; si el servicio falla deja el mensaje en cola.

        Un fallo de Cloud/Evolution (servicio caído, timeout, error 5xx)
        no debe perder el mensaje: se encola para que el cron lo reintente
        cuando el proveedor recupere disponibilidad.
        """
        try:
            provider.send_message(
                number, self.whatsapp_message or "", self.attachment_ids,
                message_type='document' if self.attachment_ids else 'text')
        except WhatsappPermanentError:
            # Errores 4xx/configuración: no tiene sentido reintentarlos.
            raise
        except Exception as e:  # noqa: BLE001 - nunca perder el mensaje
            _logger.exception(
                "WhatsApp direct send failed; enqueueing for retry")
            self._create_queue_record(number, provider, error_msg=e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Encolado por fallo de envío'),
                    'message': _(
                        'No se pudo enviar ahora (%s). El mensaje quedó en '
                        'cola para reintentarse automáticamente.') % e,
                    'type': 'warning', 'sticky': True},
            }
        return self._notify_sent(provider.name)

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
        provider._send_twilio(
            number, self.whatsapp_message or "", self.attachment_ids)
        return self._notify_sent(provider.name)

    def _send_web(self, number):
        digits = tools.clean_number_digits(number)
        message_string = parse.quote((self.whatsapp_message or "").strip())
        link = "https://web.whatsapp.com/send?phone=" + digits
        if message_string:
            link += "&text=" + message_string
        return {'type': 'ir.actions.act_url', 'url': link,
                'target': 'new', 'res_id': self.id}
