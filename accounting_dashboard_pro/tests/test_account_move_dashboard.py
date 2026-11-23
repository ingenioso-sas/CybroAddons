# -*- coding: utf-8 -*-
######################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author:  Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
########################################################################################
from datetime import date, timedelta
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError
from odoo import fields


@tagged('post_install', '-at_install')
class TestAccountMoveDashboard(TransactionCase):
    """
    Test suite for the account.move dashboard extension.
    Validates KPI calculations, period handling, and permission checks.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up test environment and initialize basic model variables
        needed across various dashboard functional tests.
        """
        super().setUpClass()
        cls.move_model = cls.env['account.move']
        cls.config_model = cls.env['account.dashboard.config']
        cls.user = cls.env.user
        cls.company = cls.env.company

    def test_dashboard_check_group(self):
        """Test access control based on groups."""
        # Current user is admin, should have 'account.group_account_readonly'
        group_readonly = 'account.group_account_readonly'
        if not self.user.has_group(group_readonly):
            self.user.write({'group_ids': [(4, self.env.ref(group_readonly).id)]})

        # Should not raise exception
        self.move_model._dashboard_check_group([group_readonly])

        # Test failure (non-existent group)
        with self.assertRaises(AccessError):
            self.move_model._dashboard_check_group(['non_existent.group'])

    def test_dashboard_get_period(self):
        """Test the _dashboard_get_period method returns correct dates."""
        today = fields.Date.context_today(self.move_model)

        # This month
        d_from, d_to = self.move_model._dashboard_get_period('this_month')
        self.assertEqual(d_from, today.replace(day=1))
        self.assertEqual(d_to, today)

        # Last month
        d_from, d_to = self.move_model._dashboard_get_period('last_month')
        expected_d_to = today.replace(day=1) - timedelta(days=1)
        expected_d_from = expected_d_to.replace(day=1)
        self.assertEqual(d_from, expected_d_from)
        self.assertEqual(d_to, expected_d_to)

        # This year
        d_from, d_to = self.move_model._dashboard_get_period('this_year')
        self.assertEqual(d_from, date(today.year, 1, 1))
        self.assertEqual(d_to, today)

        # Custom period
        d_from, d_to = self.move_model._dashboard_get_period('custom', '2023-01-01', '2023-12-31')
        self.assertEqual(d_from, date(2023, 1, 1))
        self.assertEqual(d_to, date(2023, 12, 31))

    def test_dashboard_prev_period(self):
        """Test the _dashboard_prev_period calculation."""
        date_from = date(2023, 2, 1)
        date_to = date(2023, 2, 28)

        # Custom/unknown periods keep the same-length previous range.
        prev_from, prev_to = self.move_model._dashboard_prev_period(date_from, date_to)
        self.assertEqual(prev_to, date(2023, 1, 31))
        self.assertEqual(prev_from, date(2023, 1, 4))

        # Calendar periods compare against the same calendar period.
        prev_from, prev_to = self.move_model._dashboard_prev_period(
            date(2023, 11, 1), date(2023, 11, 23), 'this_month')
        self.assertEqual((prev_from, prev_to), (date(2023, 10, 1), date(2023, 10, 23)))

        prev_from, prev_to = self.move_model._dashboard_prev_period(
            date(2023, 10, 1), date(2023, 12, 31), 'last_quarter')
        self.assertEqual((prev_from, prev_to), (date(2023, 7, 1), date(2023, 9, 30)))

        prev_from, prev_to = self.move_model._dashboard_prev_period(
            date(2023, 1, 1), date(2023, 11, 23), 'this_year')
        self.assertEqual((prev_from, prev_to), (date(2022, 1, 1), date(2022, 11, 23)))

    def test_get_dashboard_kpi_data(self):
        """Test get_dashboard_kpi_data returns correct keys without crashing."""
        # Ensure user has the required group to bypass check
        group_invoice = self.env.ref('account.group_account_invoice')
        self.user.write({'group_ids': [(4, group_invoice.id)]})

        params = {
            'period': 'this_month',
            'company_ids': [self.company.id],
        }
        data = self.move_model.get_dashboard_kpi_data(params)
        
        # Check that the basic structure is returned
        self.assertIn('invoices', data)
        self.assertIn('bills', data)
        self.assertIn('overdue_receivable', data)
        self.assertIn('overdue_payable', data)
        self.assertIn('currency_id', data)
        self.assertIn('currency_symbol', data)
        self.assertIn('period', data)

    def test_dashboard_capabilities(self):
        """Financial KPIs must be available to readonly users and managers."""
        self.assertFalse(self.move_model._dashboard_can_view_financials({}))
        self.assertFalse(self.move_model._dashboard_can_view_financials({
            'is_invoicing': True, 'is_basic': True,
        }))
        self.assertTrue(self.move_model._dashboard_can_view_financials({
            'is_readonly': True,
        }))
        self.assertTrue(self.move_model._dashboard_can_view_financials({
            'is_manager': True,
        }))

    def _create_internal_user(self, login, groups):
        base_group = self.env.ref('base.group_user')
        group_ids = [base_group.id] + [self.env.ref(xmlid).id for xmlid in groups]
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'group_ids': [(6, 0, group_ids)],
        })

    def test_manager_sees_financial_kpis(self):
        """A manager must get financial KPI keys even without readonly group."""
        manager = self._create_internal_user(
            'adp_manager@example.com', ['account.group_account_manager'])
        params = {'period': 'this_month', 'company_ids': [self.company.id]}
        data = self.env['account.move'].with_user(manager).get_dashboard_kpi_data(params)
        self.assertTrue(data['user_groups']['is_manager'])
        self.assertIn('revenue', data)
        self.assertIn('expenses', data)
        self.assertIn('cash_balance', data)
        self.assertIn('total_receivable', data)
        self.assertIn('runway_days', data)

    def test_non_accounting_user_cannot_read_dashboard(self):
        """A plain internal user must not access dashboard data."""
        user = self._create_internal_user('adp_plain@example.com', [])
        params = {'period': 'this_month', 'company_ids': [self.company.id]}
        with self.assertRaises(AccessError):
            self.env['account.move'].with_user(user).get_dashboard_kpi_data(params)
        with self.assertRaises(AccessError):
            self.env['account.move'].with_user(user).get_account_journal_ids(params)

    def _create_invoice(self, move_type, amount, invoice_date=None):
        partner = self.env['res.partner'].create({'name': 'ADP Test Partner'})
        invoice_date = invoice_date or fields.Date.context_today(self.move_model)
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': invoice_date,
            'date': invoice_date,
            'invoice_line_ids': [(0, 0, {
                'name': 'ADP test line',
                'quantity': 1,
                'price_unit': amount,
            })],
        })
        move.action_post()
        return move

    def test_revenue_and_expenses_are_net_of_refunds(self):
        """KPIs and the monthly chart must subtract credit notes."""
        params = {'period': 'this_month', 'company_ids': [self.company.id]}
        before_kpi = self.move_model.get_dashboard_kpi_data(params)
        before_chart = self.move_model.get_dashboard_chart_data(params)

        self._create_invoice('out_invoice', 100)
        self._create_invoice('out_refund', 25)
        self._create_invoice('in_invoice', 200)
        self._create_invoice('in_refund', 50)

        after_kpi = self.move_model.get_dashboard_kpi_data(params)
        after_chart = self.move_model.get_dashboard_chart_data(params)

        self.assertAlmostEqual(
            after_kpi['revenue']['amount'] - before_kpi['revenue']['amount'],
            75.0, places=2)
        self.assertAlmostEqual(
            after_kpi['expenses']['amount'] - before_kpi['expenses']['amount'],
            150.0, places=2)
        self.assertAlmostEqual(
            after_chart['revenue'][-1] - before_chart['revenue'][-1],
            75.0, places=2)
        self.assertAlmostEqual(
            after_chart['expenses'][-1] - before_chart['expenses'][-1],
            150.0, places=2)

    def test_cashflow_waterfall_closing_is_ledger_balance(self):
        """The waterfall closing must match the real cash balance."""
        params = {'period': 'this_month', 'company_ids': [self.company.id]}
        date_from, date_to = self.move_model._dashboard_get_period('this_month')
        data = self.move_model.get_dashboard_cashflow_waterfall(params)
        expected = self.move_model._dashboard_cash_balance(
            [self.company.id], date_to)
        self.assertEqual(data['types'][-1], 'total')
        self.assertAlmostEqual(data['values'][-1], expected, places=2)

    def test_dashboard_months_helper(self):
        months = self.move_model._dashboard_months(
            date(2023, 11, 1), date(2024, 2, 1))
        self.assertEqual(months, ['2023-11', '2023-12', '2024-01', '2024-02'])

    def test_dashboard_cap_param(self):
        self.assertEqual(self.move_model._dashboard_cap_param(0, 10, 50), 1)
        self.assertEqual(self.move_model._dashboard_cap_param(999, 10, 50), 50)
        self.assertEqual(self.move_model._dashboard_cap_param('bad', 10, 50), 10)

    def test_cashflow_days_are_capped(self):
        params = {
            'period': 'this_month',
            'company_ids': [self.company.id],
            'days': 100000,
        }
        data = self.move_model.get_dashboard_cashflow(params)
        self.assertLessEqual(len(data['labels']), 366)

    def test_mixed_currency_scope_uses_reporting_currency(self):
        eur = self.env.ref('base.EUR')
        foreign_currency = (
            self.env.ref('base.USD')
            if self.company.currency_id == eur
            else eur
        )
        foreign_company = self.env['res.company'].create({
            'name': 'ADP FX Test Company',
            'currency_id': foreign_currency.id,
        })
        self.env.user.company_ids = [(4, foreign_company.id)]
        requested = [self.company.id, foreign_company.id]
        info = self.move_model._dashboard_currency_info(requested)
        self.assertTrue(info['mixed_currency'])
        self.assertIn(foreign_company.id, info['excluded_company_ids'])
        self.assertNotIn(
            foreign_company.id,
            self.move_model._dashboard_company_ids(requested))

    def test_open_move_total_includes_prior_and_excludes_future(self):
        today = fields.Date.context_today(self.move_model)
        before = self.move_model._dashboard_open_move_total(
            [self.company.id], 'out_invoice', today)
        try:
            self._create_invoice(
                'out_invoice', 123.0,
                invoice_date=today - timedelta(days=40))
            after_prior = self.move_model._dashboard_open_move_total(
                [self.company.id], 'out_invoice', today)
            self._create_invoice(
                'out_invoice', 77.0,
                invoice_date=today + timedelta(days=30))
            after_future = self.move_model._dashboard_open_move_total(
                [self.company.id], 'out_invoice', today)
        except UserError:
            self.skipTest("Period is locked")
        self.assertAlmostEqual(after_prior - before, 123.0, places=2)
        self.assertAlmostEqual(after_future - before, 123.0, places=2)

    def test_config_is_idempotent(self):
        first = self.config_model.get_or_create_config()
        second = self.config_model.get_or_create_config()
        self.assertEqual(first['id'], second['id'])

    def test_budget_endpoint_has_expected_shape(self):
        data = self.move_model.get_dashboard_budget_vs_actual({
            'period': 'this_month',
            'company_ids': [self.company.id],
        })
        self.assertIn('available', data)
        self.assertIn('labels', data)
        self.assertIn('budgeted', data)
        self.assertIn('actual', data)

    def test_journal_balances_use_company_currency(self):
        data = self.move_model.get_dashboard_journal_balances({
            'period': 'this_month',
            'company_ids': [self.company.id],
        })
        for journal in data:
            self.assertEqual(
                journal['currency'], self.company.currency_id.symbol)

    def test_account_invoice_analysis_action_exists(self):
        """The dashboard uses the standard Invoice Analysis action."""
        action = self.env.ref(
            'account.action_account_invoice_report_all', raise_if_not_found=False)
        self.assertTrue(action, "account.action_account_invoice_report_all is missing")

    def test_safe_change_pct(self):
        """Test safe percentage change calculation."""
        pct = self.move_model._safe_change_pct(150, 100)
        self.assertEqual(pct, 50.0)

        pct = self.move_model._safe_change_pct(50, 100)
        self.assertEqual(pct, -50.0)

        pct = self.move_model._safe_change_pct(100, 0)
        self.assertEqual(pct, 0.0)

        pct = self.move_model._safe_change_pct(0, 100)
        self.assertEqual(pct, -100.0)

        # Handling negative previous (e.g. expenses as negative)
        pct = self.move_model._safe_change_pct(150, -100)
        self.assertEqual(pct, 250.0)
