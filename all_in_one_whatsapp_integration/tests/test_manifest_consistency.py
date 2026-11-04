# -*- coding: utf-8 -*-
"""Consistencia del manifiesto: ficheros declarados existen, sin cron
duplicado, modelos con access rights."""
import ast
import csv
import os
import unittest
import xml.etree.ElementTree as ET

try:
    from odoo.tests import tagged
    from odoo.tests.common import BaseCase as _OdooBase
except ImportError:  # entorno standalone sin Odoo instalado
    def tagged(*_args, **_kwargs):
        def decorator(obj):
            return obj
        return decorator

    from unittest import TestCase as _OdooBase

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _manifest():
    with open(os.path.join(ROOT, "__manifest__.py")) as f:
        return ast.literal_eval(f.read())


@tagged('standard', 'at_install')
class TestManifestConsistency(_OdooBase):
    # BaseCase (odoo.tests) asigna test_tags/test_module automáticamente
    # y aporta __unittest_skip__ que exige OdooSuite.
    def test_data_files_exist(self):
        manifest = _manifest()
        missing = [p for p in manifest.get("data", [])
                   if not os.path.isfile(os.path.join(ROOT, p))]
        self.assertEqual(missing, [], "Ficheros data faltantes: %s" % missing)

    def test_no_duplicate_cron_ids(self):
        seen = {}
        dupes = set()
        for fname in ["data/cron.xml"]:
            path = os.path.join(ROOT, fname)
            if not os.path.isfile(path):
                continue
            for rec in ET.parse(path).getroot().iter("record"):
                rid = rec.get("id")
                if rid in seen:
                    dupes.add(rid)
                seen[rid] = fname
        self.assertEqual(dupes, set())
        # El cron duplicado antiguo debe haber desaparecido
        self.assertFalse(os.path.exists(
            os.path.join(ROOT, "data", "whatsapp_queue_cron.xml")))

    def test_spanish_translation_exists(self):
        po = os.path.join(ROOT, "i18n", "es.po")
        self.assertTrue(os.path.isfile(po), "Falta i18n/es.po")
        with open(po, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Language: es", content)
        self.assertIn("Enviar por Whatsapp", content)

    def test_models_imported(self):
        with open(os.path.join(ROOT, "models", "__init__.py")) as f:
            init = f.read()
        for mod in ["whatsapp_provider", "whatsapp_queue_message",
                    "whatsapp_service", "whatsapp_tools"]:
            self.assertIn(mod, init)
        # Modelo legacy eliminado: no debe importarse ni existir
        self.assertNotIn("whatsapp_message", init.replace(
            "whatsapp_queue_message", ""))
        self.assertFalse(os.path.exists(
            os.path.join(ROOT, "models", "whatsapp_message.py")))

    def test_access_rights_cover_models(self):
        with open(os.path.join(ROOT, "security", "ir.model.access.csv")) as f:
            rows = list(csv.DictReader(f))
        models = {r["model_id:id"] for r in rows}
        for expected in ["model_whatsapp_provider",
                         "model_whatsapp_queue_message",
                         "model_send_whatsapp_message"]:
            self.assertIn(expected, models)


if __name__ == "__main__":
    unittest.main()
