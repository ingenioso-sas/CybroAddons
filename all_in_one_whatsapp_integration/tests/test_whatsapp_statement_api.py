# -*- coding: utf-8 -*-
# Copyright 2026 PayOnline Ing
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Partner helpers and high-level WhatsApp send service."""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestWhatsappMessageService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.provider = cls.env["whatsapp.provider"].with_context(
            active_test=False
        ).search(
            [("code", "=", "evolution"), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not cls.provider:
            cls.provider = cls.env["whatsapp.provider"].create(
                {
                    "code": "evolution",
                    "name": "Evolution API",
                    "company_id": cls.company.id,
                }
            )
        cls.provider.active = True
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "WhatsApp Service Customer",
                "phone": "+573001234567",
                "company_id": cls.company.id,
                "whatsapp_opt_in": True,
            }
        )

    def test_partner_number_and_consent(self):
        self.assertEqual(
            self.partner._get_whatsapp_number(), "+573001234567"
        )
        self.assertTrue(self.partner._can_send_whatsapp())
        self.partner.whatsapp_opt_in = False
        self.assertFalse(self.partner._can_send_whatsapp())

    def test_recipient_falls_back_to_commercial_partner(self):
        company_partner = self.env["res.partner"].create(
            {
                "name": "WhatsApp Service Company",
                "is_company": True,
                "phone": "+573009998877",
                "company_id": self.company.id,
                "whatsapp_opt_in": True,
            }
        )
        contact = self.env["res.partner"].create(
            {
                "name": "WhatsApp Service Contact",
                "parent_id": company_partner.id,
                "company_id": self.company.id,
            }
        )
        self.assertEqual(
            contact._get_whatsapp_recipient(), company_partner
        )
        self.assertTrue(contact._can_send_whatsapp())

    def test_default_provider_for_company(self):
        provider = self.env["whatsapp.provider"].get_default_for_company(
            self.company
        )
        self.assertTrue(provider)
        self.assertTrue(provider.active)
        self.assertEqual(provider.company_id, self.company)

    def test_send_to_partner_creates_a_queue_record(self):
        result = self.env["whatsapp.message.service"].send_to_partner(
            self.partner,
            "Mensaje de prueba",
            company=self.company,
            model="res.partner",
            res_id=self.partner.id,
        )
        self.assertTrue(result["sent"])
        self.assertTrue(result["queue"])
        self.assertEqual(result["phone"], "+573001234567")
        self.assertEqual(result["queue"].phone, "+573001234567")
        self.assertEqual(result["queue"].partner_id, self.partner)
        self.assertIn("Mensaje de prueba", result["queue"].message)

    def test_send_to_partner_requires_opt_in(self):
        self.partner.whatsapp_opt_in = False
        result = self.env["whatsapp.message.service"].send_to_partner(
            self.partner, "Mensaje"
        )
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "no_destination")
        self.assertFalse(result["queue"])

    def test_send_to_number_rejects_invalid_phone(self):
        result = self.env["whatsapp.message.service"].send_to_number(
            "123", "Mensaje"
        )
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "no_destination")
