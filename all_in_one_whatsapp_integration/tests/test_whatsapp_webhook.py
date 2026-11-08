# -*- coding: utf-8 -*-
"""Pruebas del webhook y del espejo de Discuss (anti-eco)."""
from markupsafe import Markup

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.all_in_one_whatsapp_integration.controllers.\
    all_in_one_whatsapp_integration import Webhook


@tagged('post_install', '-at_install')
class TestWhatsappWebhook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['whatsapp.provider'].with_context(
            active_test=False).search([('code', '=', 'cloud')], limit=1)
        cls.provider.active = True
        cls.env['ir.config_parameter'].sudo().set_param(
            'all_in_one_whatsapp_integration.whatsapp_discuss_mirror', '1')
        cls.contact = cls.env['res.partner'].create({
            'name': 'Cliente WhatsApp',
            'phone': '+573001112233',
        })
        cls.agent_user = cls.env['res.users'].create({
            'name': 'Agente WhatsApp',
            'login': 'agente_whatsapp_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.channel = cls.env['discuss.channel'].create({
            'name': 'Cliente WhatsApp',
            'channel_type': 'channel',
            'phone': '+573001112233',
            'group_public_id': cls.env.ref('base.group_user').id,
        })

    def _queue_count(self):
        return self.env['whatsapp.queue.message'].search_count(
            [('phone', '=', '+573001112233')])

    def test_internal_message_is_mirrored(self):
        self.channel.with_user(self.agent_user).message_post(
            body=Markup('<p>hola desde el agente</p>'),
            author_id=self.agent_user.partner_id.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        queue = self.env['whatsapp.queue.message'].search(
            [('phone', '=', '+573001112233')])
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.partner_id, self.contact)
        self.assertNotIn('<p>', queue.message)

    def test_inbound_message_is_not_echoed(self):
        before = self._queue_count()
        self.channel.with_context(whatsapp_inbound=True).message_post(
            author_id=self.contact.id,
            body='<p>mensaje entrante</p>',
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        self.assertEqual(self._queue_count(), before)

    def test_contact_message_without_context_is_not_echoed(self):
        before = self._queue_count()
        self.channel.message_post(
            author_id=self.contact.id,
            body='<p>mensaje del contacto</p>',
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        self.assertEqual(self._queue_count(), before)

    def test_extract_text_payloads(self):
        self.assertEqual(
            Webhook._extract_text({'text': {'body': 'hola'}}), 'hola')
        self.assertEqual(
            Webhook._extract_text({'button': {'text': 'Sí'}}), 'Sí')
        self.assertEqual(
            Webhook._extract_text({'interactive': {
                'button_reply': {'title': 'Opción 1'}}}), 'Opción 1')
        self.assertEqual(
            Webhook._extract_text({'image': {'caption': 'foto'}}), 'foto')
        self.assertIn('image recibido',
                      Webhook._extract_text({'type': 'image'}))
