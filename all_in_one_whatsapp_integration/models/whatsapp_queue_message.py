# -*- coding: utf-8 -*-
"""COLA ÚNICA de mensajes WhatsApp (todos los proveedores encolables).

Contrato del módulo:
- `whatsapp.queue.message` es el ÚNICO modelo de cola. El antiguo
  `whatsapp.message` quedó eliminado (ver data/cleanup_legacy.xml).
- Entradas: wizard (opción Encolar), espejo de Discuss y
  `create_queue_message()` como punto único de API.
- Solo se procesan proveedores ACTIVOS (`provider_id.active`).
- Cada fallo guarda su causa en `error_msg`; `action_retry` devuelve
  a pendiente (con tope de reintentos configurable).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WhatsappQueueMessage(models.Model):
    _name = 'whatsapp.queue.message'
    _description = 'Cola Única de Mensajes de WhatsApp'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', string='Contacto',
                                 index=True, ondelete='set null')
    provider_id = fields.Many2one(
        'whatsapp.provider', string='Proveedor', index=True,
        ondelete='restrict',
        help="Canal de envío. Solo proveedores habilitados.")
    phone = fields.Char('Teléfono', required=True, index=True)
    message = fields.Text('Mensaje')
    attachment_ids = fields.Many2many('ir.attachment', string='Adjuntos')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('error', 'Error'),
    ], string='Estado', default='pending', index=True)
    error_msg = fields.Text('Causa del fallo', readonly=True)
    date_sent = fields.Datetime('Fecha de envío', readonly=True)
    retry_count = fields.Integer('Reintentos', default=0)
    model = fields.Char('Modelo Relacionado', index=True)
    res_id = fields.Integer('ID Relacionado', index=True)

    @api.model
    def _get_param(self, key, default=False, cast=None):
        value = self.env['ir.config_parameter'].sudo().get_param(key, default)
        if cast and value not in (False, None):
            try:
                return cast(value)
            except (TypeError, ValueError):
                return default
        return value

    @api.model
    def create_queue_message(self, phone, message, provider_code,
                             partner_id=False, attachment_ids=False,
                             model=False, res_id=False):
        """Punto ÚNICO de entrada para encolar mensajes WhatsApp."""
        if not phone:
            raise ValidationError(_("Se requiere el teléfono destino."))
        if not (message or "").strip() and not attachment_ids:
            raise ValidationError(
                _("Se requiere mensaje o adjunto para encolar."))
        provider = self.env['whatsapp.provider'].sudo().search(
            [('code', '=', provider_code)], limit=1)
        if not provider:
            raise ValidationError(
                _("Proveedor desconocido: %s") % provider_code)
        if not provider.active:
            raise ValidationError(
                _("El proveedor '%s' está deshabilitado.") % provider.name)
        if provider_code not in ('cloud', 'evolution'):
            raise ValidationError(
                _("El proveedor '%s' es de envío directo y no usa la cola.")
                % provider.name)
        if isinstance(partner_id, models.BaseModel):
            partner_id = partner_id.id
        return self.create({
            'partner_id': partner_id or False,
            'provider_id': provider.id,
            'phone': phone,
            'message': message or "",
            'attachment_ids': [(6, 0, attachment_ids.ids)]
            if attachment_ids else False,
            'model': model,
            'res_id': res_id,
            'state': 'pending',
        })

    @api.model
    def _process_queue(self, limit=None):
        """Procesa pendientes de proveedores activos. Nunca revienta."""
        limit = limit or self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_limit', 20,
            cast=int)
        max_retries = self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_max_retries', 5,
            cast=int)
        pending = self.search(
            [('state', '=', 'pending'),
             ('retry_count', '<', max_retries),
             ('provider_id.active', '=', True)],
            limit=limit, order='create_date asc')
        for msg in pending:
            try:
                msg.action_send_message()
            except Exception as e:  # noqa: BLE001 - el cron debe continuar
                _logger.exception("Queue _process_queue error id=%s", msg.id)
                msg.write({'state': 'error', 'error_msg': str(e)[:2000],
                           'retry_count': msg.retry_count + 1})
        return True

    def action_send_message(self):
        """Envía un registro por su proveedor y guarda la causa si falla."""
        for record in self:
            if not record.provider_id:
                record.write({'state': 'error',
                              'error_msg': _('Sin proveedor asignado.'),
                              'retry_count': record.retry_count + 1})
                continue
            try:
                record.provider_id.send_message(
                    record.phone, record.message or "",
                    record.attachment_ids)
                record.write({'state': 'sent',
                              'date_sent': fields.Datetime.now(),
                              'error_msg': False})
            except Exception as e:
                record.write({'state': 'error',
                              'error_msg': str(e)[:2000],
                              'retry_count': record.retry_count + 1})

    def action_retry(self):
        """Devuelve a pendiente los mensajes en error (ver botón)."""
        max_retries = self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_max_retries', 5,
            cast=int)
        retryable = self.filtered(
            lambda r: r.state == 'error' and r.retry_count < max_retries)
        if not retryable:
            raise ValidationError(
                _("Nada que reintentar: sin errores o tope alcanzado."))
        retryable.write({'state': 'pending', 'error_msg': False})
        return True

    def name_get(self):
        result = []
        for rec in self:
            name = "%s · %s → %s" % (
                rec.provider_id.code if rec.provider_id else "-",
                rec.partner_id.name or rec.phone, rec.state)
            result.append((rec.id, name))
        return result
