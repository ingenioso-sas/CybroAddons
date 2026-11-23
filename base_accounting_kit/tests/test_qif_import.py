# -*- coding: utf-8 -*-
import base64
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import AccountKitCommon
from ..wizard.qif_parser import parse_qif

# Same content as the sample shipped in
# static/description/assets/screenshots/statement.qif: exports without an
# ``!Account`` section, which used to yield no transactions at all.
SAMPLE_QIF = """!Type:Bank
D14/04/2023
T2000.00
PBank-2023-02-11/1
^
!Type:Bank
D09/04/2023
T-500.00
PBank-2023-04-09/2
^
!Type:Bank
D19/06/2022
T1000.00
PBank-2023-04-21/3
^
"""


@tagged('post_install', '-at_install')
class TestQifParser(TransactionCase):
    """Unit tests for the dependency-free QIF reader."""

    def test_header_only_file(self):
        """Files without !Account sections (the common bank export) parse."""
        transactions = parse_qif(SAMPLE_QIF)
        self.assertEqual(len(transactions), 3)
        self.assertEqual(
            [transaction.amount for transaction in transactions],
            ['2000.00', '-500.00', '1000.00'])
        self.assertEqual(
            [transaction.date for transaction in transactions],
            ['14/04/2023', '09/04/2023', '19/06/2022'])
        self.assertEqual(transactions[0].payee, 'Bank-2023-02-11/1')

    def test_account_blocks_crlf_and_bytes(self):
        """!Account blocks are skipped and CRLF bytes are decoded."""
        content = (
            b"!Account\r\n"
            b"NChecking\r\n"
            b"TBank\r\n"
            b"^\r\n"
            b"!Type:Bank\r\n"
            b"D14/04/2023\r\n"
            b"T2,000.00\r\n"
            b"PProveedor SA\r\n"
            b"MCompra\r\n"
            b"^\r\n"
            b"D09/04/2023\r\n"
            b"T-500.00\r\n"
            b"^\r\n"
        )
        transactions = parse_qif(content)
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0].amount, '2,000.00')
        self.assertEqual(transactions[0].payee, 'Proveedor SA')
        self.assertEqual(transactions[0].memo, 'Compra')
        self.assertIsNone(transactions[1].payee)

    def test_ignores_non_bank_sections(self):
        """Categories and investments are not bank transactions."""
        content = """!Type:Cat
NFood
E
^
!Type:Invst
D01/02/2020
NBuy
T100.00
^
!Type:Bank
D01/02/2020
T50.00
PMarket
^
"""
        transactions = parse_qif(content)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].amount, '50.00')
        self.assertEqual(transactions[0].payee, 'Market')

    def test_two_digit_year_and_spaces(self):
        """Quicken-style ``7/ 9'98`` dates are normalized."""
        transactions = parse_qif("!Type:Bank\nD7/ 9'98\nT10.00\n^\n")
        self.assertEqual(transactions[0].date, '07/09/1998')

    def test_missing_final_caret(self):
        """A transaction is kept when the file has no trailing caret."""
        transactions = parse_qif(
            "!Type:Bank\nD14/04/2023\nT10.00\nPNo caret")
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].payee, 'No caret')

    def test_utf8_bom(self):
        """A UTF-8 BOM must not hide the first section header."""
        content = ('\ufeff' + SAMPLE_QIF).encode('utf-8')
        self.assertEqual(len(parse_qif(content)), 3)

    def test_empty_content(self):
        self.assertEqual(parse_qif(b''), [])


@tagged('post_install', '-at_install')
class TestQifImport(AccountKitCommon):
    """End-to-end tests for the .qif branch of the import wizard."""

    def _import(self, content, file_name='statement.qif'):
        wizard = self.env['import.bank.statement'].create({
            'attachment': base64.b64encode(content).decode('ascii'),
            'file_name': file_name,
            'journal_id': self.bank_journal.id,
        })
        return wizard.action_statement_import()

    def test_import_sample_qif(self):
        """The bundled sample (no !Account section) creates statements."""
        result = self._import(SAMPLE_QIF.encode('utf-8'))
        self.assertEqual(result['res_model'], 'account.bank.statement')
        statements = self.env['account.bank.statement'].search(
            [('journal_id', '=', self.bank_journal.id)], order='id')
        self.assertEqual(len(statements), 3)
        self.assertEqual(
            statements.mapped('balance_end_real'), [2000.0, -500.0, 1000.0])
        self.assertEqual(
            [statement.date for statement in statements],
            [date(2023, 4, 14), date(2023, 4, 9), date(2022, 6, 19)])
        self.assertEqual(result['res_id'], statements[-1].id)

    def test_import_with_account_section_matches_partner(self):
        """Files with !Account sections import once and match partners."""
        partner = self.env['res.partner'].create({'name': 'Proveedor QIF'})
        content = (
            b"!Account\r\n"
            b"NChecking\r\n"
            b"TBank\r\n"
            b"^\r\n"
            b"!Type:Bank\r\n"
            b"D14/04/2023\r\n"
            b"T150.00\r\n"
            b"PProveedor QIF\r\n"
            b"^\r\n"
        )
        self._import(content)
        lines = self.env['account.bank.statement.line'].search(
            [('journal_id', '=', self.bank_journal.id)])
        self.assertEqual(len(lines), 1, "Transactions must not be duplicated")
        self.assertEqual(lines.partner_id, partner)
        self.assertEqual(lines.payment_ref, 'Proveedor QIF')

    def test_import_without_transactions_raises(self):
        with self.assertRaises(ValidationError):
            self._import(b"!Type:Cat\nNFood\nE\n^\n")
