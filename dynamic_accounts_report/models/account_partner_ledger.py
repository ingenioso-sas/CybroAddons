# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Swetha Anand (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
import calendar
import io
import json
from dateutil.relativedelta import relativedelta
import xlsxwriter
from odoo import api, fields, models
from datetime import datetime
from odoo.tools import date_utils


class AccountPartnerLedger(models.TransientModel):
    """For creating Partner Ledger report"""
    _name = 'account.partner.ledger'
    _description = 'Partner Ledger Report'

    def _get_date_range(self, data_range):
        """Return the period start/end and the opening balance date."""
        today = fields.Date.today()
        opening_date = self.env.company.account_opening_date
        if not data_range:
            return False, False, opening_date
        if isinstance(data_range, dict):
            start = self._parse_date(data_range.get('start_date'))
            end = self._parse_date(data_range.get('end_date'))
            return start, end, start
        quarter_start, quarter_end = date_utils.get_quarter(today)
        if data_range == 'month':
            return today.replace(day=1), today, today.replace(day=1)
        if data_range == 'year':
            return today.replace(month=1, day=1), today, today.replace(
                month=1, day=1)
        if data_range == 'quarter':
            return quarter_start, quarter_end, quarter_start
        if data_range == 'last-month':
            start = today.replace(day=1) - relativedelta(months=1)
            end = start + relativedelta(
                day=calendar.monthrange(start.year, start.month)[1] - 1)
            return start, end, start
        if data_range == 'last-year':
            start = today.replace(month=1, day=1) - relativedelta(years=1)
            end = start.replace(month=12, day=31)
            return start, end, start
        if data_range == 'last-quarter':
            start = quarter_start - relativedelta(months=3)
            end = quarter_start - relativedelta(days=1)
            return start, end, start
        return False, False, opening_date

    @staticmethod
    def _parse_date(value):
        if not value:
            return False
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return False

    def _get_base_domain(self, account, options, journals=None,
                         reconciled=None):
        account_type_domain = []
        if not account or ('Receivable' in account and 'Payable' in account):
            account_type_domain = ['liability_payable', 'asset_receivable']
        elif 'Receivable' in account:
            account_type_domain = ['asset_receivable']
        elif 'Payable' in account:
            account_type_domain = ['liability_payable']
        option_domain = ['posted']
        if options and 'draft' in options:
            option_domain = ['posted', 'draft']
        domain = [
            ('account_type', 'in', account_type_domain),
            ('parent_state', 'in', option_domain),
        ]
        if journals:
            domain.append(('journal_id', 'in', journals))
        if reconciled == 'reconciled':
            domain.append(('reconciled', '=', True))
        elif reconciled == 'unreconciled':
            domain.append(('reconciled', '=', False))
        return domain

    def _build_report(self, partner_id=None, data_range=None, account=None,
                      options=None, journals=None, reconciled='all'):
        """Build the Partner Ledger data for the selected filters."""
        start_date, end_date, opening_date = self._get_date_range(data_range)
        base_domain = self._get_base_domain(
            account, options, journals, reconciled)
        period_domain = list(base_domain)
        if start_date:
            period_domain.append(('date', '>=', start_date))
        if end_date:
            period_domain.append(('date', '<=', end_date))
        if partner_id:
            partner_ids = partner_id
        else:
            partner_ids = self.env['account.move.line'].search(
                period_domain).mapped('partner_id').ids
        partner_dict = {}
        partner_totals = {}
        currency_id = self.env.company.currency_id.symbol
        for partner in self.env['res.partner'].browse(partner_ids).sorted(
                key=lambda item: (item.display_name or '', item.id)):
            partner_domain = period_domain + [('partner_id', '=', partner.id)]
            move_line_ids = self.env['account.move.line'].search(
                partner_domain, order='date, id')
            opening_domain = list(base_domain) + [
                ('partner_id', '=', partner.id)]
            if opening_date:
                opening_domain.append(('date', '<', opening_date))
            else:
                opening_domain.append(('id', '=', 0))
            opening_lines = self.env['account.move.line'].search(
                opening_domain)
            opening_debit = round(sum(opening_lines.mapped('debit')), 2)
            opening_credit = round(sum(opening_lines.mapped('credit')), 2)
            initial_balance = opening_debit - opening_credit
            move_line_list = []
            for move_line in move_line_ids:
                move_line_data = move_line.read(
                    ['date', 'move_name', 'account_type', 'debit', 'credit',
                     'date_maturity', 'account_id', 'journal_id', 'move_id',
                     'matching_number', 'amount_currency'])
                move_line_data[0]['code'] = move_line.account_id.code or ''
                move_line_data[0]['jrnl'] = move_line.journal_id.code or ''
                move_line_list.append(move_line_data)
            if not move_line_list and not initial_balance:
                continue
            total_debit = round(sum(move_line_ids.mapped('debit')), 2)
            total_credit = round(sum(move_line_ids.mapped('credit')), 2)
            partner_dict[partner.name] = move_line_list
            partner_totals[partner.name] = {
                'total_debit': total_debit,
                'total_credit': total_credit,
                'currency_id': currency_id,
                'partner_id': partner.id,
                'move_name': 'Initial Balance',
                'initial_debit': opening_debit,
                'initial_credit': opening_credit,
                'initial_balance': round(initial_balance, 2),
                'closing_balance': round(
                    initial_balance + total_debit - total_credit, 2),
            }
        partner_dict['partner_totals'] = partner_totals
        return partner_dict

    @api.model
    def view_report(self, option, tag):
        """Load the initial Partner Ledger and its filter metadata."""
        result = self._build_report()
        result['journal_ids'] = self.env['account.journal'].search_read(
            [], ['name'])
        return result

    @api.model
    def get_filter_values(self, partner_id, data_range, account, options,
                          journals=None, reconciled=None):
        """Return the Partner Ledger rows for the selected filters."""
        return self._build_report(
            partner_id=partner_id, data_range=data_range, account=account,
            options=options, journals=journals, reconciled=reconciled)

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an Excel report based on the provided data.

        :param data: The data used to generate the report.
        :type data: str (JSON format)

        :param response: The response object to write the report to.
        :type response: object

        :param report_name: The name of the report.
        :type report_name: str

        :return: None
        """
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        start_date = data['filters']['start_date'] if data['filters']['start_date'] else ''
        end_date = data['filters']['end_date'] if data['filters']['end_date'] else ''
        sheet = workbook.add_worksheet()

        # Define formats
        head = workbook.add_format({'font_size': 15, 'align': 'center', 'bold': True})
        head_highlight = workbook.add_format({'font_size': 10, 'align': 'center', 'bold': True})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px', 'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px', 'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_body = workbook.add_format({'align': 'center', 'bold': True, 'font_size': '10px'})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': '10px', 'border': 1, 'border_color': 'black'})
        side_heading_sub.set_indent(1)
        txt_name = workbook.add_format({'font_size': '10px', 'border': 1})
        txt_name.set_indent(2)

        # Set column widths
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 15)
        sheet.set_column(3, 3, 15)

        # Write headers and filters
        col = 0
        sheet.write('A1:B1', report_name, head)
        sheet.write('B3:B4', 'Date Range', filter_head)
        sheet.write('B4:B4', 'Partners', filter_head)
        sheet.write('B5:B4', 'Accounts', filter_head)
        sheet.write('B6:B4', 'Options', filter_head)
        sheet.write('B7:B4', 'Journals', filter_head)
        sheet.write('B8:B4', 'Reconciliation', filter_head)

        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}", filter_body)

        if data['filters']['partner']:
            display_names = [partner.get('display_name', 'undefined') for partner in data['filters']['partner']]
            display_names_str = ', '.join(display_names)
            sheet.merge_range('C4:G4', display_names_str, filter_body)

        if data['filters']['account']:
            account_keys = list(data['filters']['account'].keys())
            account_keys_str = ', '.join(account_keys)
            sheet.merge_range('C5:G5', account_keys_str, filter_body)

        if data['filters']['options']:
            option_keys = list(data['filters']['options'].keys())
            option_keys_str = ', '.join(option_keys)
            sheet.merge_range('C6:G6', option_keys_str, filter_body)
        if data['filters'].get('journal'):
            sheet.merge_range(
                'C7:G7', ', '.join(data['filters']['journal']), filter_body)
        reconciled = data['filters'].get('reconciled', 'all')
        reconciled_label = {
            'reconciled': 'Reconciled Only',
            'unreconciled': 'Unreconciled Only',
        }.get(reconciled, 'All Entries')
        sheet.merge_range('C8:G8', reconciled_label, filter_body)

        # Define a helper function to format numbers with thousand separators
        def format_number(value):
            if value is None:
                return "0.00"
            return "{:,.2f}".format(float(value))

        # Process partner data
        if data and report_action == 'dynamic_accounts_report.action_partner_ledger':
            sheet.write(8, col, ' ', sub_heading)
            sheet.write(8, col + 1, 'JNRL', sub_heading)
            sheet.write(8, col + 2, 'Account', sub_heading)
            sheet.merge_range('D9:E9', 'Ref', sub_heading)
            sheet.merge_range('F9:G9', 'Due Date', sub_heading)
            sheet.merge_range('H9:I9', 'Debit', sub_heading)
            sheet.merge_range('J9:K9', 'Credit', sub_heading)
            sheet.merge_range('L9:M9', 'Balance', sub_heading)

            row = 8
            # Ensure data['partners'] is iterable; default to empty list if None
            partners = data.get('partners', []) or []
            for partner in partners:
                row += 1
                # Format partner totals
                total_debit = data['total'][partner]['total_debit'] if data['total'] and partner in data['total'] else 0
                total_credit = data['total'][partner]['total_credit'] if data['total'] and partner in data[
                    'total'] else 0
                balance = total_debit - total_credit

                sheet.write(row, col, partner, txt_name)
                sheet.write(row, col + 1, ' ', txt_name)
                sheet.write(row, col + 2, ' ', txt_name)
                sheet.merge_range(row, col + 3, row, col + 4, ' ', txt_name)
                sheet.merge_range(row, col + 5, row, col + 6, ' ', txt_name)
                sheet.merge_range(row, col + 7, row, col + 8, format_number(total_debit), txt_name)
                sheet.merge_range(row, col + 9, row, col + 10, format_number(total_credit), txt_name)
                sheet.merge_range(row, col + 11, row, col + 12, format_number(balance), txt_name)

                # Handle initial balance
                initial_balance = data['total'][partner]['initial_balance'] if data['total'] and partner in data[
                    'total'] else 0
                if initial_balance != 0:
                    row += 1
                    initial_debit = data['total'][partner]['initial_debit'] if data['total'] and partner in data[
                        'total'] else 0
                    initial_credit = data['total'][partner]['initial_credit'] if data['total'] and partner in data[
                        'total'] else 0

                    sheet.write(row, col, '', txt_name)
                    sheet.write(row, col + 1, ' ', txt_name)
                    sheet.write(row, col + 2, ' ', txt_name)
                    sheet.merge_range(row, col + 3, row, col + 4, 'Initial Balance', head_highlight)
                    sheet.merge_range(row, col + 5, row, col + 6, ' ', txt_name)
                    sheet.merge_range(row, col + 7, row, col + 8, format_number(initial_debit), txt_name)
                    sheet.merge_range(row, col + 9, row, col + 10, format_number(initial_credit), txt_name)
                    sheet.merge_range(row, col + 11, row, col + 12, format_number(initial_balance), txt_name)

                # Process move lines for the partner
                for rec in data['data'][partner]:
                    row += 1
                    sheet.write(row, col, rec[0]['date'], txt_name)
                    sheet.write(row, col + 1, rec[0]['jrnl'], txt_name)
                    sheet.write(row, col + 2, rec[0]['code'], txt_name)
                    sheet.merge_range(row, col + 3, row, col + 4, rec[0]['move_name'], txt_name)
                    sheet.merge_range(row, col + 5, row, col + 6, rec[0]['date_maturity'] or '', txt_name)
                    sheet.merge_range(row, col + 7, row, col + 8, format_number(rec[0]['debit']), txt_name)
                    sheet.merge_range(row, col + 9, row, col + 10, format_number(rec[0]['credit']), txt_name)
                    sheet.merge_range(row, col + 11, row, col + 12, ' ', txt_name)

            # Grand totals
            row += 1
            # Ensure grand_total values are numbers
            grand_total_debit = data['grand_total']['total_debit'] if data['grand_total'] and data['grand_total'][
                'total_debit'] is not None else 0
            grand_total_credit = data['grand_total']['total_credit'] if data['grand_total'] and data['grand_total'][
                'total_credit'] is not None else 0
            grand_balance = grand_total_debit - grand_total_credit

            sheet.merge_range(row, col, row, col + 6, 'Total', filter_head)
            sheet.merge_range(row, col + 7, row, col + 8, format_number(grand_total_debit), filter_head)
            sheet.merge_range(row, col + 9, row, col + 10, format_number(grand_total_credit), filter_head)
            sheet.merge_range(row, col + 11, row, col + 12, format_number(grand_balance), filter_head)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()