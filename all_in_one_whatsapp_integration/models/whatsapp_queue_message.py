# -*- coding: utf-8 -*-
"""COLA ÚNICA de mensajes WhatsApp (todos los proveedores encolables).

Contrato del módulo:
- `whatsapp.queue.message` es el ÚNICO modelo de cola. El antiguo
  `whatsapp.message` quedó eliminado (ver data/cleanup_legacy.xml).
- Entradas: wizard (opción Encolar), espejo de Discuss y
  `create_queue_message()` como punto único de API.
- Solo se procesan proveedores ACTIVOS (`provider_id.active`).
- Cada fallo guarda su causa en `error_msg`. Si aún no se alcanzó el tope
  de reintentos el mensaje SIGUE en `pending` y el cron lo reintenta solo
  cuando el proveedor vuelve a estar disponible; al agotar el tope pasa a
  `error`. `action_retry` lo devuelve a pendiente y reinicia el contador.
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
                _("El proveedor '%s' está deshabilitado. Actívelo en "
                  "WhatsApp → Proveedores (o en Ajustes → WhatsApp → "
                  "Canales habilitados).") % provider.name)
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
    def _get_max_retries(self):
        return self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_max_retries', 5,
            cast=int)

    @api.model
    def _process_queue(self, limit=None):
        """Procesa pendientes de proveedores activos. Nunca revienta."""
        limit = limit or self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_limit', 20,
            cast=int)
        max_retries = self._get_max_retries()
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
                msg._register_failure(e)
        return True

    def _register_failure(self, error):
        """Guarda la causa y decide si el mensaje sigue reintentándose.

        Mientras no se alcance el tope configurado el mensaje CONTINÚA en
        ``pending`` para que el cron lo reintente solo cuando el proveedor
        vuelva a estar disponible. Solo al agotar los reintentos pasa a
        ``error``.
        """
        self.ensure_one()
        retry_count = self.retry_count + 1
        max_retries = self._get_max_retries()
        self.write({
            'state': 'error' if retry_count >= max_retries else 'pending',
            'error_msg': str(error)[:2000],
            'retry_count': retry_count,
        })
        return retry_count < max_retries

    def action_send_message(self):
        """Envía un registro por su proveedor y guarda la causa si falla."""
        for record in self:
            if not record.provider_id:
                record._register_failure(_('Sin proveedor asignado.'))
                continue
            try:
                record.provider_id.send_message(
                    record.phone, record.message or "",
                    record.attachment_ids)
                record.write({'state': 'sent',
                              'date_sent': fields.Datetime.now(),
                              'error_msg': False})
            except Exception as e:
                record._register_failure(e)
        return True

    def action_retry(self):
        """Devuelve a pendiente los mensajes en error (ver botón).

        Reinicia el contador para abrir un nuevo ciclo de reintentos
        automáticos después de corregir la causa (p. ej. el proveedor caído).
        """
        retryable = self.filtered(lambda r: r.state == 'error')
        if not retryable:
            raise ValidationError(
                _("Nada que reintentar: no hay mensajes en error."))
        retryable.write({'state': 'pending', 'error_msg': False,
                         'retry_count': 0})
        return True

    @api.depends('provider_id', 'partner_id', 'phone', 'state')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s · %s → %s" % (
                rec.provider_id.code if rec.provider_id else "-",
                rec.partner_id.name or rec.phone, rec.state)
