# -*- coding: utf-8 -*-
"""Regresión: los fallos de envío deben seguir en cola para reintentarse.

Antes, ``action_send_message`` pasaba el mensaje a ``error`` en el primer
fallo y el cron (que solo busca ``pending``) nunca lo reintentaba. Ahora
permanece ``pending`` hasta agotar el tope configurado.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


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
        cls.partner = cls.env['res.partner'].create({
            'name': 'WhatsApp Queue Test',
            'phone': '+573001234567',
        })

    def _create_message(self, message='hola'):
        return self.Queue.create_queue_message(
            phone='+573001234567', message=message,
            provider_code='evolution', partner_id=self.partner)

    def test_failure_keeps_pending_until_max_retries(self):
        msg = self._create_message()
        with patch.object(type(self.provider), 'send_message',
                          side_effect=UserError('servicio caído')):
            msg.action_send_message()
            self.assertEqual(msg.state, 'pending')
            self.assertEqual(msg.retry_count, 1)
            self.assertIn('servicio caído', msg.error_msg)
            msg.action_send_message()
            self.assertEqual(msg.state, 'pending')
            self.assertEqual(msg.retry_count, 2)
            msg.action_send_message()
        self.assertEqual(msg.retry_count, 3)
        self.assertEqual(msg.state, 'error')

    def test_process_queue_retries_and_sends(self):
        msg = self._create_message('reintento')
        with patch.object(type(self.provider), 'send_message',
                          side_effect=UserError('sin servicio')):
            self.Queue._process_queue(limit=10)
        self.assertEqual(msg.state, 'pending')
        self.assertEqual(msg.retry_count, 1)
        with patch.object(type(self.provider), 'send_message',
                          return_value=True):
            self.Queue._process_queue(limit=10)
        self.assertEqual(msg.state, 'sent')
        self.assertTrue(msg.date_sent)

    def test_retry_resets_counter(self):
        msg = self._create_message('manual')
        msg.write({'state': 'error', 'retry_count': 3,
                   'error_msg': 'caído'})
        msg.action_retry()
        self.assertEqual(msg.state, 'pending')
        self.assertEqual(msg.retry_count, 0)
        self.assertFalse(msg.error_msg)

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
