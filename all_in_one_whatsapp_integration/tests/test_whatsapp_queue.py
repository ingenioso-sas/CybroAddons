# -*- coding: utf-8 -*-
"""Regresión de la cola de WhatsApp: reintentos, backoff, permisos y limpieza."""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.all_in_one_whatsapp_integration.models.whatsapp_exceptions \
    import WhatsappPermanentError


@tagged('post_install', '-at_install')
class TestWhatsappQueueRetry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Queue = cls.env['whatsapp.queue.message']
        cls.provider = cls.env['whatsapp.provider'].with_context(
            active_test=False).search([('code', '=', 'evolution')], limit=1)
        if not cls.provider:
            cls.provider = cls.env['whatsapp.provider'].create({
                'code': 'evolution',
                'name': 'Evolution API',
            })
        cls.provider.active = True
        cls.env['ir.config_parameter'].sudo().set_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_max_retries', '3')
        cls.env['ir.config_parameter'].sudo().set_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_retry_delay', '1')
        cls.partner = cls.env['res.partner'].create({
            'name': 'WhatsApp Queue Test',
            'phone': '+573001234567',
        })

    def _create_message(self, message='hola', **kwargs):
        return self.Queue.create_queue_message(
            phone='+573001234567', message=message,
            provider_code='evolution', partner_id=self.partner, **kwargs)

    def test_failure_keeps_pending_until_max_retries(self):
        msg = self._create_message()
        with patch.object(type(self.provider), 'send_message',
                          side_effect=UserError('servicio caído')):
            msg.action_send_message()
            self.assertEqual(msg.state, 'pending')
            self.assertEqual(msg.retry_count, 1)
            self.assertIn('servicio caído', msg.error_msg)
            self.assertTrue(msg.next_attempt)
            msg.action_send_message()
            self.assertEqual(msg.state, 'pending')
            self.assertEqual(msg.retry_count, 2)
            msg.action_send_message()
        self.assertEqual(msg.retry_count, 3)
        self.assertEqual(msg.state, 'error')
        self.assertTrue(msg.permanent is False)

    def test_permanent_error_stops_immediately(self):
        msg = self._create_message()
        with patch.object(type(self.provider), 'send_message',
                          side_effect=WhatsappPermanentError('400 bad request')):
            msg.action_send_message()
        self.assertEqual(msg.state, 'error')
        self.assertTrue(msg.permanent)
        self.assertEqual(msg.retry_count, 1)

    def test_process_queue_retries_and_sends(self):
        msg = self._create_message('reintento')
        with patch.object(type(self.provider), 'send_message',
                          side_effect=UserError('sin servicio')):
            self.Queue._process_queue(limit=10)
        self.assertEqual(msg.state, 'pending')
        self.assertEqual(msg.retry_count, 1)
        # Simular que ya venció el backoff.
        msg.write({'next_attempt': False})
        with patch.object(type(self.provider), 'send_message',
                          return_value=True):
            self.Queue._process_queue(limit=10)
        self.assertEqual(msg.state, 'sent')
        self.assertTrue(msg.date_sent)
        self.assertFalse(msg.next_attempt)

    def test_retry_resets_counter(self):
        msg = self._create_message('manual')
        msg.write({'state': 'error', 'retry_count': 3,
                   'error_msg': 'caído', 'permanent': True,
                   'next_attempt': fields.Datetime.now()})
        msg.action_retry()
        self.assertEqual(msg.state, 'pending')
        self.assertEqual(msg.retry_count, 0)
        self.assertFalse(msg.error_msg)
        self.assertFalse(msg.permanent)
        self.assertFalse(msg.next_attempt)

    def test_direct_send_failure_enqueues(self):
        wizard = self.env['send.whatsapp.message'].create({
            'sale_user_id': self.partner.id,
            'whatsapp_message': 'mensaje directo',
            'provider_id': self.provider.id,
            'delivery': 'now',
        })
        with patch.object(type(self.provider), 'send_message',
                          side_effect=UserError('servicio caído')):
            action = wizard.action_send_custom_message()
        self.assertEqual(action.get('tag'), 'display_notification')
        queued = self.Queue.search([
            ('phone', '=', '+573001234567'),
            ('message', '=', 'mensaje directo'),
        ])
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued.state, 'pending')
        self.assertIn('servicio caído', queued.error_msg)

    def test_direct_send_permanent_does_not_enqueue(self):
        wizard = self.env['send.whatsapp.message'].create({
            'sale_user_id': self.partner.id,
            'whatsapp_message': 'mensaje permanente',
            'provider_id': self.provider.id,
            'delivery': 'now',
        })
        with patch.object(type(self.provider), 'send_message',
                          side_effect=WhatsappPermanentError('400')):
            with self.assertRaises(WhatsappPermanentError):
                wizard.action_send_custom_message()
        self.assertFalse(self.Queue.search([
            ('message', '=', 'mensaje permanente'),
        ]))

    def test_create_queue_requires_e164(self):
        with self.assertRaises(ValidationError):
            self.Queue.create_queue_message(
                phone='3001234567', message='x',
                provider_code='evolution')

    def test_template_queue_message(self):
        msg = self._create_message(
            message='',
            message_type='template',
            template_name='order_update',
            template_language='es',
            template_components=[{
                'type': 'body',
                'parameters': [{'type': 'text', 'text': 'Pedido 1'}],
            }],
        )
        self.assertEqual(msg.message_type, 'template')
        self.assertEqual(msg.template_name, 'order_update')
        self.assertIn('parameters', msg.template_components)

    def test_template_requires_name(self):
        with self.assertRaises(ValidationError):
            self._create_message(
                message='', message_type='template', template_name=False)

    def test_cleanup_removes_old_sent(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'all_in_one_whatsapp_integration.whatsapp_queue_retention_days',
            '1')
        msg = self._create_message('viejo')
        old_date = fields.Datetime.subtract(fields.Datetime.now(), days=2)
        msg.write({'state': 'sent', 'date_sent': old_date})
        self.Queue._cleanup_queue()
        self.assertFalse(msg.exists())

    def test_queue_access_requires_group(self):
        user = self.env['res.users'].create({
            'name': 'Sin WhatsApp',
            'login': 'sin_whatsapp_queue_test',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.Queue.with_user(user).search([])
        user.write({'group_ids': [(4, self.env.ref(
            'all_in_one_whatsapp_integration.group_whatsapp_user').id)]})
        self.Queue.with_user(user).search([])

    def test_multi_company_record_rule(self):
        company_a = self.env['res.company'].create({'name': 'WA Company A'})
        company_b = self.env['res.company'].create({'name': 'WA Company B'})
        Provider = self.env['whatsapp.provider']
        Provider.create({
            'code': 'cloud',
            'name': 'Cloud A',
            'company_id': company_a.id,
            'active': True,
        })
        Provider.create({
            'code': 'cloud',
            'name': 'Cloud B',
            'company_id': company_b.id,
            'active': True,
        })
        msg_a = self.Queue.with_context(
            allowed_company_ids=[company_a.id]).create_queue_message(
            phone='+573001234567', message='A', provider_code='cloud',
            partner_id=self.partner, company_id=company_a.id)
        msg_b = self.Queue.with_context(
            allowed_company_ids=[company_b.id]).create_queue_message(
            phone='+573001234567', message='B', provider_code='cloud',
            partner_id=self.partner, company_id=company_b.id)
        user = self.env['res.users'].create({
            'name': 'Operador A',
            'login': 'operador_wa_a',
            'company_id': company_a.id,
            'company_ids': [(6, 0, [company_a.id])],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(
                    'all_in_one_whatsapp_integration.group_whatsapp_user').id,
            ])],
        })
        visible = self.Queue.with_user(user).search([])
        self.assertIn(msg_a, visible)
        self.assertNotIn(msg_b, visible)
