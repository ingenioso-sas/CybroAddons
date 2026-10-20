# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
MAX_RETRIES = 5


class WhatsappQueueMessage(models.Model):
    _name = 'whatsapp.queue.message'
    _description = 'Cola de Mensajes de WhatsApp'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', string='Contacto',
                                 required=True, index=True, ondelete='cascade')
    phone = fields.Char('Teléfono', required=True, index=True)
    message = fields.Text('Mensaje', required=True)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('error', 'Error'),
    ], string='Estado', default='pending', index=True)
    error_msg = fields.Text('Mensaje de Error')
    date_sent = fields.Datetime('Fecha de Envío', readonly=True)
    retry_count = fields.Integer('Reintentos', default=0)
    model = fields.Char('Modelo Relacionado', index=True)
    res_id = fields.Integer('ID Relacionado', index=True)

    @api.model
    def create_queue_message(self, partner_id, phone, message,
                             model=None, res_id=None):
        """Punto ÚNICO de entrada para encolar mensajes WhatsApp."""
        if not phone or not message:
            raise ValidationError(
                _("Phone and message are required to queue WhatsApp."))
        if isinstance(partner_id, models.BaseModel):
            partner_id = partner_id.id
        return self.create({
            'partner_id': partner_id,
            'phone': phone,
            'message': message,
            'model': model,
            'res_id': res_id,
            'state': 'pending',
        })

    @api.model
    def _process_queue(self, limit=20):
        pending = self.search([('state', '=', 'pending'),
                               ('retry_count', '<', MAX_RETRIES)],
                              limit=limit, order='create_date asc')
        for msg in pending:
            try:
                msg.action_send_message()
            except Exception as e:  # noqa: BLE001 - cron must continue
                _logger.exception("Queue _process_queue error id=%s", msg.id)
                msg.write({'state': 'error', 'error_msg': str(e)[:2000],
                           'retry_count': msg.retry_count + 1})
        return True

    def action_send_message(self):
        from ..wizard.whatsapp_mode_message import WhatsappModeMessage
        for record in self:
            try:
                helper = WhatsappModeMessage(self.env)
                response = helper.action_send_custom_message(
                    record.phone, record.message or "")
                status = getattr(response, 'status_code', 0) or 0
                if status in (200, 201):
                    record.write({'state': 'sent',
                                  'date_sent': fields.Datetime.now(),
                                  'error_msg': False})
                else:
                    text = getattr(response, 'text', 'Error desconocido')
                    record.write({'state': 'error',
                                  'error_msg': str(text)[:2000],
                                  'retry_count': record.retry_count + 1})
            except Exception as e:
                record.write({'state': 'error', 'error_msg': str(e)[:2000],
                              'retry_count': record.retry_count + 1})

    def action_retry(self):
        retryable = self.filtered(
            lambda r: r.state == 'error' and r.retry_count < MAX_RETRIES)
        retryable.write({'state': 'pending', 'error_msg': False})
        return True

    def name_get(self):
        result = []
        for rec in self:
            name = "%s - %s" % (rec.partner_id.name or rec.phone, rec.state)
            result.append((rec.id, name))
        return result
