# -*- coding: utf-8 -*-
"""COLA ÚNICA de mensajes WhatsApp (todos los proveedores encolables).

Contrato del módulo:
- `whatsapp.queue.message` es el ÚNICO modelo de cola. El antiguo
  `whatsapp.message` quedó eliminado (ver migración 19.0.1.0.2).
- Entradas: wizard (opción Encolar), espejo de Discuss y
  `create_queue_message()` como punto único de API.
- Solo se procesan proveedores ACTIVOS (`provider_id.active`).
- Cada fallo guarda su causa en `error_msg`. Los errores transitorios
  permanecen en `pending` con backoff exponencial hasta el tope; los
  errores permanentes (4xx) pasan directamente a `error`.
"""
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import whatsapp_tools as tools
from .whatsapp_exceptions import WhatsappPermanentError

_logger = logging.getLogger(__name__)

QUEUE_PROVIDER_CODES = ('cloud', 'evolution')


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
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    phone = fields.Char('Teléfono', required=True, index=True)
    message = fields.Text('Mensaje')
    message_type = fields.Selection(
        [('text', 'Texto'), ('document', 'Documento'),
         ('template', 'Plantilla')],
        string='Tipo', default='text', required=True)
    template_name = fields.Char(string='Plantilla de WhatsApp')
    template_language = fields.Char(string='Idioma plantilla', default='es')
    template_components = fields.Text(
        string='Componentes de plantilla (JSON)',
        help="JSON con los componentes de la plantilla aprobada.")
    attachment_ids = fields.Many2many('ir.attachment', string='Adjuntos')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('error', 'Error'),
    ], string='Estado', default='pending', index=True)
    error_msg = fields.Text('Causa del fallo', readonly=True)
    date_sent = fields.Datetime('Fecha de envío', readonly=True)
    retry_count = fields.Integer('Reintentos', default=0)
    permanent = fields.Boolean(
        'Fallo permanente', readonly=True, copy=False,
        help="El proveedor devolvió un error 4xx no recuperable.")
    last_attempt = fields.Datetime(
        'Último intento', readonly=True, copy=False)
    next_attempt = fields.Datetime(
        'Próximo intento', readonly=True, copy=False, index=True)
    provider_message_id = fields.Char(
        'ID del mensaje en el proveedor', readonly=True, copy=False,
        index=True)
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
    def _get_max_retries(self):
        return max(1, self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_max_retries', 5,
            cast=int))

    @api.model
    def _get_retry_delay(self):
        return max(1, self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_retry_delay', 5,
            cast=int))

    @api.model
    def _get_retention_days(self):
        return self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_retention_days',
            90, cast=int)

    @api.model
    def _should_notify_source(self):
        value = self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_notify_source_on_error',
            '1')
        return str(value).lower() in ('1', 'true', 'yes')

    @api.model
    def create_queue_message(self, phone, message, provider_code,
                             partner_id=False, attachment_ids=False,
                             model=False, res_id=False, message_type='text',
                             template_name=False, template_language='es',
                             template_components=False, company_id=False):
        """Punto ÚNICO de entrada para encolar mensajes WhatsApp."""
        normalized_phone = tools.normalize_e164(phone)
        if not tools.is_valid_e164(normalized_phone):
            raise ValidationError(
                _("Teléfono inválido (use E.164, ej. +573001234567): %s")
                % phone)
        if isinstance(company_id, models.BaseModel):
            company_id = company_id.id
        if company_id and int(company_id) not in self.env.companies.ids:
            raise ValidationError(
                _("No tiene acceso a la compañía indicada para encolar."))
        provider = self.env['whatsapp.provider'].sudo().search(
            [('code', '=', provider_code),
             ('company_id', '=', company_id or self.env.company.id)],
            limit=1)
        if not provider:
            raise ValidationError(
                _("Proveedor desconocido o de otra compañía: %s")
                % provider_code)
        if not provider.active:
            raise ValidationError(
                _("El proveedor '%s' está deshabilitado. Actívelo en "
                  "WhatsApp → Proveedores (o en Ajustes → WhatsApp → "
                  "Canales habilitados).") % provider.name)
        if provider_code not in QUEUE_PROVIDER_CODES:
            raise ValidationError(
                _("El proveedor '%s' es de envío directo y no usa la cola.")
                % provider.name)
        if isinstance(partner_id, models.BaseModel):
            partner_id = partner_id.id
        if isinstance(attachment_ids, models.BaseModel):
            attachment_ids = attachment_ids.ids
        attachment_ids = attachment_ids or []
        if template_name:
            message_type = 'template'
        elif attachment_ids and message_type == 'text':
            message_type = 'document'
        if message_type == 'template':
            if not template_name:
                raise ValidationError(
                    _("Indique el nombre de la plantilla de WhatsApp."))
            if attachment_ids:
                raise ValidationError(
                    _("Las plantillas de WhatsApp no admiten adjuntos."))
        elif not (message or "").strip() and not attachment_ids:
            raise ValidationError(
                _("Se requiere mensaje o adjunto para encolar."))
        if template_components and not isinstance(template_components, str):
            template_components = json.dumps(template_components)
        return self.create({
            'partner_id': partner_id or False,
            'provider_id': provider.id,
            'company_id': company_id or provider.company_id.id
            or self.env.company.id,
            'phone': normalized_phone,
            'message': message or "",
            'message_type': message_type,
            'template_name': template_name or False,
            'template_language': template_language or 'es',
            'template_components': template_components or False,
            'attachment_ids': [(6, 0, attachment_ids)],
            'model': model,
            'res_id': res_id,
            'state': 'pending',
        })

    @api.constrains('phone')
    def _check_phone(self):
        for record in self:
            if record.phone and not (
                    tools.is_valid_e164(record.phone)
                    or tools.normalize_inbound_phone(record.phone)):
                raise ValidationError(
                    _("Teléfono inválido en la cola: %s") % record.phone)

    @api.constrains('message_type', 'template_name', 'template_components')
    def _check_template(self):
        for record in self:
            if record.message_type == 'template' and not record.template_name:
                raise ValidationError(
                    _("Indique el nombre de la plantilla de WhatsApp."))
            if record.template_components:
                try:
                    json.loads(record.template_components)
                except (TypeError, ValueError) as e:
                    raise ValidationError(
                        _("Componentes de plantilla inválidos: %s") % e)

    @api.model
    def _process_queue(self, limit=None):
        """Procesa pendientes vencidos de proveedores activos."""
        configured_limit = self._get_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_limit', 20,
            cast=int)
        limit = max(1, min(int(limit or configured_limit or 20), 200))
        max_retries = self._get_max_retries()
        now = fields.Datetime.now()
        pending = self.search(
            [('state', '=', 'pending'),
             ('retry_count', '<', max_retries),
             ('provider_id.active', '=', True),
             '|', ('next_attempt', '=', False),
             ('next_attempt', '<=', now)],
            limit=limit, order='create_date asc')
        for msg in pending:
            try:
                with self.env.cr.savepoint():
                    msg.action_send_message()
            except Exception as e:  # noqa: BLE001 - el cron debe continuar
                _logger.exception("Queue _process_queue error id=%s", msg.id)
                msg._register_failure(e)
        return True

    def _register_failure(self, error):
        """Guarda la causa y decide si el mensaje sigue reintentándose."""
        self.ensure_one()
        now = fields.Datetime.now()
        retry_count = self.retry_count + 1
        max_retries = self._get_max_retries()
        permanent = isinstance(error, WhatsappPermanentError)
        state = 'error' if permanent or retry_count >= max_retries \
            else 'pending'
        next_attempt = False
        if state == 'pending':
            delay = min(
                self._get_retry_delay() * (2 ** (retry_count - 1)),
                24 * 60,
            )
            next_attempt = now + timedelta(minutes=delay)
        self.write({
            'state': state,
            'error_msg': str(error)[:2000],
            'retry_count': retry_count,
            'permanent': permanent,
            'last_attempt': now,
            'next_attempt': next_attempt,
        })
        _logger.warning(
            "WhatsApp queue failure id=%s provider=%s retry=%s permanent=%s "
            "error=%s", self.id,
            self.provider_id.code or "-", retry_count, permanent,
            str(error)[:500])
        if state == 'error':
            self._notify_source_error(error)
        return state == 'pending'

    def _notify_source_error(self, error):
        """Avisa en el documento origen (si existe) que el envío falló."""
        if not self._should_notify_source() or not self.model or not self.res_id:
            return
        try:
            record = self.env[self.model].sudo().browse(self.res_id).exists()
            if record and hasattr(record, 'message_post'):
                record.message_post(
                    body=_("No se pudo enviar el mensaje de WhatsApp a %s: %s")
                    % (self.phone, error),
                    subtype_xmlid='mail.mt_note')
        except Exception:  # noqa: BLE001 - nunca romper el flujo principal
            _logger.exception(
                "No se pudo notificar el fallo de WhatsApp id=%s", self.id)

    def _try_lock(self):
        """Reclama el registro para evitar envíos duplicados concurrentes."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM whatsapp_queue_message "
                    "WHERE id = %s FOR UPDATE NOWAIT", (self.id,))
                return bool(self.env.cr.fetchone())
        except Exception:  # noqa: BLE001 - otro worker lo tiene bloqueado
            return False

    def action_send_message(self):
        """Envía un registro por su proveedor y guarda la causa si falla."""
        for record in self:
            if record.state == 'sent':
                continue
            if not record._try_lock():
                _logger.info(
                    "WhatsApp queue id=%s is locked by another worker; "
                    "skipping.", record.id)
                continue
            if not record.provider_id:
                record._register_failure(_('Sin proveedor asignado.'))
                continue
            try:
                response = record.provider_id.send_message(
                    record.phone, record.message or "",
                    record.attachment_ids,
                    message_type=record.message_type,
                    template_name=record.template_name,
                    template_language=record.template_language,
                    template_components=record.template_components)
                now = fields.Datetime.now()
                record.write({
                    'state': 'sent',
                    'date_sent': now,
                    'error_msg': False,
                    'permanent': False,
                    'next_attempt': False,
                    'last_attempt': now,
                    'provider_message_id': (
                        record.provider_id._extract_message_id(response)
                        or record.provider_message_id),
                })
            except Exception as e:
                record._register_failure(e)
        return True

    def action_retry(self):
        """Devuelve a pendiente los mensajes en error (ver botón)."""
        retryable = self.filtered(lambda r: r.state == 'error')
        if not retryable:
            raise ValidationError(
                _("Nada que reintentar: no hay mensajes en error."))
        retryable.write({
            'state': 'pending',
            'error_msg': False,
            'retry_count': 0,
            'permanent': False,
            'next_attempt': False,
        })
        return True

    @api.model
    def _cleanup_queue(self):
        """Purga enviados/errores antiguos y adjuntos propios de la cola."""
        days = self._get_retention_days()
        if not days or days <= 0:
            return True
        now = fields.Datetime.now()
        sent = self.search([
            ('state', '=', 'sent'),
            ('date_sent', '!=', False),
            ('date_sent', '<', now - timedelta(days=days)),
        ])
        errors = self.search([
            ('state', '=', 'error'),
            '|',
            '&', ('last_attempt', '!=', False),
            ('last_attempt', '<', now - timedelta(days=days * 2)),
            '&', ('last_attempt', '=', False),
            ('create_date', '<', now - timedelta(days=days * 2)),
        ])
        records = sent | errors
        attachments = records.mapped('attachment_ids').filtered(
            lambda a: a.res_model in (
                'send.whatsapp.message', 'whatsapp.queue.message'))
        count = len(records)
        records.unlink()
        if attachments:
            attachments.sudo().unlink()
        _logger.info(
            "WhatsApp queue cleanup: %s registros y %s adjuntos eliminados.",
            count, len(attachments))
        return True

    @api.depends('provider_id', 'partner_id', 'phone', 'state')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s · %s → %s" % (
                rec.provider_id.code if rec.provider_id else "-",
                rec.partner_id.name or rec.phone, rec.state)
