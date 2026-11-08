# -*- coding: utf-8 -*-
"""Pruebas de proveedores: payloads, adjuntos, plantillas y errores."""
import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.all_in_one_whatsapp_integration.models import \
    whatsapp_provider as provider_module
from odoo.addons.all_in_one_whatsapp_integration.models.whatsapp_exceptions \
    import WhatsappPermanentError


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


@tagged('post_install', '-at_install')
class TestWhatsappProvider(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Provider = cls.env['whatsapp.provider'].with_context(
            active_test=False)
        cls.cloud = Provider.search([('code', '=', 'cloud')], limit=1)
        cls.cloud.write({
            'active': True,
            'cloud_bearer_token': 'test-token',
            'cloud_phone_number_id': '123456',
            'cloud_graph_version': 'v27.0',
        })
        cls.evolution = Provider.search([('code', '=', 'evolution')], limit=1)
        cls.evolution.write({
            'active': True,
            'evolution_base_url': 'https://evolution.example.com',
            'evolution_instance': 'instance',
            'evolution_apikey': 'apikey',
        })
        cls.twilio = Provider.search([('code', '=', 'twilio')], limit=1)
        cls.twilio.write({
            'active': True,
            'twilio_account_sid': 'AC123',
            'twilio_auth_token': 'token',
            'twilio_whatsapp_number': '+15550000000',
        })
        cls.attachment_1 = cls.env['ir.attachment'].create({
            'name': 'a.pdf',
            'datas': base64.b64encode(b'aaa'),
            'mimetype': 'application/pdf',
        })
        cls.attachment_2 = cls.env['ir.attachment'].create({
            'name': 'b.pdf',
            'datas': base64.b64encode(b'bbb'),
            'mimetype': 'application/pdf',
        })

    def test_cloud_text_payload_and_graph_version(self):
        response = FakeResponse(data={'messages': [{'id': 'wamid.1'}]})
        with patch.object(provider_module.requests, 'post',
                          return_value=response) as mocked:
            result = self.cloud.send_message('+573001234567', 'hola')
        mocked.assert_called_once()
        args, kwargs = mocked.call_args
        self.assertEqual(
            args[0], 'https://graph.facebook.com/v27.0/123456/messages')
        self.assertEqual(kwargs['json']['type'], 'text')
        self.assertEqual(kwargs['json']['text']['body'], 'hola')
        self.assertIn('Bearer test-token',
                      kwargs['headers']['Authorization'])
        self.assertEqual(
            self.cloud._extract_message_id(result), 'wamid.1')

    def test_cloud_template_payload(self):
        response = FakeResponse(data={'messages': [{'id': 'wamid.2'}]})
        components = [{'type': 'body', 'parameters': [
            {'type': 'text', 'text': 'Pedido 1'}]}]
        with patch.object(provider_module.requests, 'post',
                          return_value=response) as mocked:
            self.cloud.send_message(
                '+573001234567', '', message_type='template',
                template_name='order_update', template_language='es',
                template_components=components)
        payload = mocked.call_args.kwargs['json']
        self.assertEqual(payload['type'], 'template')
        self.assertEqual(payload['template']['name'], 'order_update')
        self.assertEqual(payload['template']['language']['code'], 'es')
        self.assertEqual(payload['template']['components'], components)

    def test_cloud_multiple_attachments(self):
        response = FakeResponse(data={'messages': [{'id': 'wamid.3'}]})
        attachments = self.attachment_1 | self.attachment_2
        with patch.object(provider_module.requests, 'post',
                          return_value=response) as mocked:
            self.cloud.send_message(
                '+573001234567', 'caption', attachments,
                message_type='document')
        self.assertEqual(mocked.call_count, 2)
        first = mocked.call_args_list[0].kwargs['json']
        second = mocked.call_args_list[1].kwargs['json']
        self.assertEqual(first['document']['caption'], 'caption')
        self.assertEqual(second['document']['caption'], '')

    def test_cloud_4xx_is_permanent(self):
        with patch.object(provider_module.requests, 'post',
                          return_value=FakeResponse(400, text='bad request')):
            with self.assertRaises(WhatsappPermanentError):
                self.cloud.send_message('+573001234567', 'hola')

    def test_cloud_5xx_is_retryable(self):
        with patch.object(provider_module.requests, 'post',
                          return_value=FakeResponse(500, text='server error')):
            with self.assertRaises(UserError) as error:
                self.cloud.send_message('+573001234567', 'hola')
            self.assertNotIsInstance(error.exception, WhatsappPermanentError)

    def test_evolution_multiple_attachments(self):
        response = FakeResponse(200, data={'key': {'id': 'evo-1'}})
        with patch('odoo.addons.all_in_one_whatsapp_integration.wizard.'
                   'whatsapp_mode_message.requests.post',
                   return_value=response) as mocked:
            self.evolution.send_message(
                '+573001234567', 'caption',
                self.attachment_1 | self.attachment_2,
                message_type='document')
        self.assertEqual(mocked.call_count, 2)
        first = mocked.call_args_list[0].kwargs['json']
        second = mocked.call_args_list[1].kwargs['json']
        self.assertEqual(first['caption'], 'caption')
        self.assertEqual(second['caption'], '')
        self.assertEqual(first['mediatype'], 'document')

    def test_twilio_media_url(self):
        with patch('twilio.rest.Client') as client_cls:
            client = client_cls.return_value
            client.messages.create.return_value = object()
            self.twilio.send_message(
                '+573001234567', 'hola', self.attachment_1)
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(kwargs['to'], 'whatsapp:+573001234567')
        self.assertEqual(len(kwargs['media_url']), 1)
        self.assertIn('/web/content/', kwargs['media_url'][0])

    def test_unsupported_template_for_evolution(self):
        with self.assertRaises(WhatsappPermanentError):
            self.evolution.send_message(
                '+573001234567', '', message_type='template',
                template_name='hello')
