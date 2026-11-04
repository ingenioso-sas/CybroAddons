# -*- coding: utf-8 -*-
"""Tests puros (sin DB): validación E.164 y limpieza de números.

Ejecutables con pytest standalone y también desde Odoo
(con @tagged los descubre el runner de Odoo).
"""
import importlib.util
import os
import unittest

try:
    from odoo.tests import tagged
    from odoo.tests.common import BaseCase as _OdooBase
except ImportError:  # entorno standalone sin Odoo instalado
    def tagged(*_args, **_kwargs):
        def decorator(obj):
            return obj
        return decorator

    from unittest import TestCase as _OdooBase

_TOOLS = os.path.join(os.path.dirname(__file__), "..", "models",
                      "whatsapp_tools.py")


def _load():
    spec = importlib.util.spec_from_file_location("whatsapp_tools", _TOOLS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tools = _load()


@tagged('standard', 'at_install')
class TestWhatsappTools(_OdooBase):
    # BaseCase (odoo.tests) asigna test_tags/test_module automáticamente
    # y aporta __unittest_skip__ que exige OdooSuite.
    def test_valid_e164(self):
        self.assertTrue(tools.is_valid_e164("+573001234567"))
        self.assertTrue(tools.is_valid_e164("+57 300 123 4567"))

    def test_invalid_e164(self):
        for bad in ["", "3001234567", "+12", "+abc", None]:
            self.assertFalse(tools.is_valid_e164(bad or ""))

    def test_clean_digits(self):
        self.assertEqual(
            tools.clean_number_digits("+57 300-123 4567"), "573001234567")

    def test_validate_raises_on_empty(self):
        with self.assertRaises(ValueError):
            tools.validate_e164_or_raise("")

    def test_validate_raises_without_plus(self):
        with self.assertRaises(ValueError):
            tools.validate_e164_or_raise("3001234567")

    def test_validate_ok(self):
        self.assertEqual(
            tools.validate_e164_or_raise("+573001234567"), "+573001234567")


if __name__ == "__main__":
    unittest.main()
