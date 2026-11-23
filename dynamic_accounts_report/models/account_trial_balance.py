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
from datetime import datetime
import xlsxwriter
from odoo import api, fields, models
from odoo.tools.date_utils import get_month, get_fiscal_year, \
    get_quarter_number, subtract


class AccountTrialBalance(models.TransientModel):
    """For creating Trial Balance report"""
    _name = 'account.trial.balance'
    _description = 'Trial Balance Report'

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _to_float(value):
        """Return a float from a number or a formatted amount string."""
        if isinstance(value, str):
            value = value.replace(',', '')
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_date(value):
        """Convert a string date to a date object."""
        if not value:
            return False
        if hasattr(value, 'year') and not isinstance(value, str):
            return value
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return False

    @api.model
    def get_month_name(self, date):
        """Return the abbreviated month name for a date."""
        return calendar.month_abbr[date.month]

    def _get_base_domain(self, journal_list, analytic, options, method,
                         analytic_filter_mode=None):
        """Build the common domain used by all the grouped queries."""
        option_domain = ['posted']
        if options and 'draft' in options:
            option_domain = ['posted', 'draft']
        domain = [('parent_state', 'in', option_domain)]
        if journal_list:
            domain.append(('journal_id', 'in', journal_list))
        if method and 'cash' in method:
            domain.append(
                ('journal_id', 'in',
                 self.env.company.tax_cash_basis_journal_id.ids))
        analytic_mode = analytic_filter_mode or 'all'
        if analytic_mode == 'without':
            domain.append(('analytic_line_ids', '=', False))
        elif analytic_mode == 'with':
            if analytic:
                domain.append(('analytic_line_ids.account_id', 'in', analytic))
            else:
                domain.append(('analytic_line_ids', '!=', False))
        return domain

    def _get_group_totals(self, domain):
        """Return {account_id: (debit, credit)} with a single grouped query."""
        groups = self.env['account.move.line']._read_group(
            domain, groupby=['account_id'],
            aggregates=['debit:sum', 'credit:sum'])
        return {
            account.id: (debit or 0.0, credit or 0.0)
            for account, debit, credit in groups
        }

    def _get_periods(self, start_date, end_date, comparison_number,
                     comparison_type):
        """Build the displayed periods, oldest first, and the initial date."""
        start = self._to_date(start_date) or fields.Date.today()
        end = self._to_date(end_date) or start
        if comparison_type == 'year':
            start_first = get_fiscal_year(start)[0]
            end_first = get_fiscal_year(end)[1]
        else:
            start_first = start
            end_first = end
        try:
            number = int(comparison_number or 0)
        except (TypeError, ValueError):
            number = 0
        periods = []
        if number > 0 and comparison_type in ('year', 'month', 'quarter'):
            # Oldest period first so the report columns are chronological.
            for index in range(number, 0, -1):
                if comparison_type == 'year':
                    period_start = subtract(start_first, years=index)
                    period_end = subtract(end_first, years=index)
                    label = str(period_start.year)
                elif comparison_type == 'month':
                    period_start = subtract(start_first, months=index)
                    period_end = subtract(end_first, months=index)
                    label = '%s %s' % (
                        self.get_month_name(period_start), period_start.year)
                else:
                    period_start = subtract(start_first, months=index * 3)
                    period_end = subtract(end_first, months=index * 3)
                    label = 'Q %s %s' % (
                        get_quarter_number(period_start), period_start.year)
                periods.append({
                    'kind': 'dynamic',
                    'index': len(periods) + 1,
                    'label': label,
                    'start': period_start,
                    'end': period_end,
                })
        if comparison_type == 'year':
            current_label = str(start_first.year)
        elif comparison_type == 'month':
            current_label = '%s %s' % (
                self.get_month_name(start_first), start_first.year)
        elif comparison_type == 'quarter':
            current_label = 'Q %s %s' % (
                get_quarter_number(start_first), start_first.year)
        else:
            current_label = '%s - %s' % (
                start_first.strftime('%d/%m/%Y'),
                end_first.strftime('%d/%m/%Y'))
        periods.append({
            'kind': 'current',
            'index': None,
            'label': current_label,
            'start': start_first,
            'end': end_first,
        })
        initial_start = periods[0]['start'] if number > 0 else start_first
        return initial_start, periods

    def _consolidate_by_level(self, rows, accounts, level):
        """Consolidate account rows by a PUC code prefix."""
        if level <= 0:
            return rows
        accounts_by_code = {
            (account.code or '').strip(): account for account in accounts}
        grouped = {}
        for row in rows:
            code = row.get('code') or ''
            if code:
                prefix = code[:level] or code
            else:
                prefix = '__no_code__'
            if prefix not in grouped:
                account = accounts_by_code.get(prefix)
                if code:
                    name = account.name if account else 'Group'
                    label = ('%s %s' % (prefix, name)).strip()
                else:
                    name = 'No code'
                    label = name
                grouped[prefix] = {
                    'account': label,
                    'account_id': account.id if account else False,
                    'code': prefix if code else '',
                    'name': name,
                    'initial': 0.0,
                    'initial_total_debit': 0.0,
                    'initial_total_credit': 0.0,
                    'debit': 0.0,
                    'credit': 0.0,
                    'total_debit': 0.0,
                    'total_credit': 0.0,
                    'balance': 0.0,
                    'final_debit': 0.0,
                    'final_credit': 0.0,
                    'end_total_debit': 0.0,
                    'end_total_credit': 0.0,
                }
                if row.get('dynamic_date_num'):
                    grouped[prefix]['dynamic_date_num'] = row[
                        'dynamic_date_num']
            target = grouped[prefix]
            for key, value in row.items():
                if key in ('final_debit', 'final_credit', 'end_total_debit',
                           'end_total_credit', 'balance'):
                    continue
                if not isinstance(value, (int, float)):
                    continue
                if key in target:
                    target[key] += value
                elif key.startswith('dynamic_total_'):
                    target[key] = value
        for target in grouped.values():
            total_debit = target['total_debit'] + sum(
                value for key, value in target.items()
                if key.startswith('dynamic_total_debit_'))
            total_credit = target['total_credit'] + sum(
                value for key, value in target.items()
                if key.startswith('dynamic_total_credit_'))
            balance = target['initial'] + total_debit - total_credit
            target['balance'] = round(balance, 2)
            target['final_debit'] = round(
                balance if balance > 0 else 0.0, 2)
            target['final_credit'] = round(
                -balance if balance < 0 else 0.0, 2)
            target['end_total_debit'] = target['final_debit']
            target['end_total_credit'] = target['final_credit']
        return sorted(grouped.values(), key=lambda item: item['code'])

    def _filter_report_lines(self, rows, display_account):
        """Apply the Display Accounts option to the report rows."""
        if not display_account or display_account == 'all':
            return rows
        filtered = []
        for row in rows:
            if display_account == 'not_zero':
                amount = (self._to_float(row.get('final_debit')) +
                          self._to_float(row.get('final_credit')))
            else:
                amount = sum(
                    self._to_float(row.get(key)) for key in (
                        'initial', 'debit', 'credit'))
                amount += sum(
                    self._to_float(value) for key, value in row.items()
                    if key.startswith('dynamic_total_'))
            if abs(round(amount, 2)) > 0:
                filtered.append(row)
        return filtered

    def _build_report(self, start_date, end_date, comparison_number,
                      comparison_type, journal_list, analytic, options, method,
                      display_account, puc_level, account_from_code,
                      account_to_code, analytic_filter_mode):
        """Build the Trial Balance rows with grouped period queries."""
        initial_start, periods = self._get_periods(
            start_date, end_date, comparison_number, comparison_type)
        base_domain = self._get_base_domain(
            journal_list, analytic, options, method, analytic_filter_mode)
        period_totals = []
        for period in periods:
            domain = list(base_domain) + [
                ('date', '>=', period['start']),
                ('date', '<=', period['end']),
            ]
            period_totals.append(self._get_group_totals(domain))
        initial_totals = self._get_group_totals(
            list(base_domain) + [('date', '<', initial_start)])

        account_ids = set(initial_totals)
        for totals in period_totals:
            account_ids.update(totals)
        accounts = self.env['account.account'].browse(list(account_ids))
        code_from = (account_from_code or '').strip()
        code_to = (account_to_code or '').strip()
        if code_from:
            accounts = accounts.filtered(
                lambda account: (account.code or '') >= code_from)
        if code_to:
            accounts = accounts.filtered(
                lambda account: (account.code or '') <= code_to)
        try:
            level = int(puc_level or 0)
        except (TypeError, ValueError):
            level = 0

        comparison = len(periods) - 1
        dynamic_labels = {}
        if comparison:
            dynamic_labels['dynamic_date_num0'] = periods[-1]['label']
            for period in periods[:-1]:
                dynamic_labels[
                    'dynamic_date_num%s' % period['index']] = period['label']

        rows = []
        for account in accounts.sorted(
                key=lambda item: ((item.code or ''), item.id)):
            initial_debit, initial_credit = initial_totals.get(
                account.id, (0.0, 0.0))
            initial = initial_debit - initial_credit
            current_debit, current_credit = period_totals[-1].get(
                account.id, (0.0, 0.0))
            row = {
                'account': ('%s %s' % (
                    account.code or '', account.name or '')).strip(),
                'account_id': account.id,
                'code': (account.code or '').strip(),
                'name': account.name,
                'initial': round(initial, 2),
                'initial_total_debit': round(initial_debit, 2),
                'initial_total_credit': round(initial_credit, 2),
                'debit': round(current_debit, 2),
                'credit': round(current_credit, 2),
                'total_debit': round(current_debit, 2),
                'total_credit': round(current_credit, 2),
            }
            total_debit = current_debit
            total_credit = current_credit
            for index, totals in enumerate(period_totals[:-1], start=1):
                debit, credit = totals.get(account.id, (0.0, 0.0))
                row['dynamic_total_debit_%s' % index] = round(debit, 2)
                row['dynamic_total_credit_%s' % index] = round(credit, 2)
                total_debit += debit
                total_credit += credit
            balance = initial + total_debit - total_credit
            final_debit = balance if balance > 0 else 0.0
            final_credit = -balance if balance < 0 else 0.0
            row.update({
                'balance': round(balance, 2),
                'final_debit': round(final_debit, 2),
                'final_credit': round(final_credit, 2),
                'end_total_debit': round(final_debit, 2),
                'end_total_credit': round(final_credit, 2),
            })
            if comparison:
                row['dynamic_date_num'] = dynamic_labels
            rows.append(row)

        rows = self._consolidate_by_level(rows, accounts, level)
        return self._filter_report_lines(rows, display_account)

    # ---------------------------------------------------------------------
    # Report entry points
    # ---------------------------------------------------------------------
    @api.model
    def view_report(self, display_account='movement', puc_level='0',
                    account_from_code='', account_to_code='',
                    analytic=None, analytic_filter_mode='all'):
        """Generate the initial Trial Balance for the current month."""
        today = fields.Date.today()
        start_date, end_date = get_month(today)
        rows = self._build_report(
            start_date, end_date, 0, None, [], analytic or [], None, {},
            display_account, puc_level, account_from_code, account_to_code,
            analytic_filter_mode)
        journal = {
            'journal_ids': self.env['account.journal'].search_read(
                [], ['name']),
            'analytic_ids': self.env['account.analytic.account'].search_read(
                [], ['name']),
        }
        return rows, journal

    @api.model
    def get_filter_values(self, start_date, end_date, comparison_number,
                          comparison_type, journal_list, analytic, options,
                          method, display_account=None, puc_level=None,
                          account_from_code=None, account_to_code=None,
                          analytic_filter_mode=None):
        """Return the Trial Balance rows for the selected filters."""
        return self._build_report(
            start_date, end_date, comparison_number, comparison_type,
            journal_list, analytic, options, method, display_account,
            puc_level, account_from_code, account_to_code,
            analytic_filter_mode)

    # ---------------------------------------------------------------------
    # XLSX
    # ---------------------------------------------------------------------
    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """Generate the Trial Balance XLSX file."""
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        start_date = data['filters']['start_date'] if \
            data['filters']['start_date'] else ''
        end_date = data['filters']['end_date'] if \
            data['filters']['end_date'] else ''
        head = workbook.add_format(
            {'font_size': 15, 'align': 'center', 'bold': True})
        sheet = workbook.add_worksheet()
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_body = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px'})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': '10px',
             'border': 1,
             'border_color': 'black'})
        side_heading_sub.set_indent(1)
        total_format = workbook.add_format(
            {'font_size': '10px', 'border': 1, 'bold': True})
        txt_name = workbook.add_format({'font_size': '10px', 'border': 1})
        txt_name.set_indent(2)
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 12, 15)
        sheet.write('A1:b1', report_name, head)
        sheet.write('B3:b4', 'Date Range', filter_head)
        sheet.write('B4:b4', 'Comparison', filter_head)
        sheet.write('B5:b4', 'Journal', filter_head)
        sheet.write('B6:b4', 'Account', filter_head)
        sheet.write('B7:b4', 'Option', filter_head)
        sheet.write('B8:b4', 'Display Accounts', filter_head)
        sheet.write('B9:b4', 'PUC Level', filter_head)
        sheet.write('B10:b4', 'PUC Range', filter_head)
        sheet.write('B11:b4', 'Analytic', filter_head)
        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}",
                              filter_body)
        if data['filters']['comparison_number_range']:
            sheet.merge_range('C4:G4',
                              f"{data['filters']['comparison_type']} : {data['filters']['comparison_number_range']}",
                              filter_body)
        if data['filters']['journal']:
            display_names = [journal for
                             journal in data['filters']['journal']]
            display_names_str = ', '.join(display_names)
            sheet.merge_range('C5:G5', display_names_str, filter_body)
        if data['filters']['account']:
            account_keys = [account.get('display_name', 'undefined') for
                            account in data['filters']['account']]
            account_keys_str = ', '.join(account_keys)
            sheet.merge_range('C6:G6', account_keys_str, filter_body)
        if data['filters']['options']:
            option_keys = list(data['filters']['options'].keys())
            option_keys_str = ', '.join(option_keys)
            sheet.merge_range('C7:G7', option_keys_str, filter_body)
        display_account = data['filters'].get('display_account', 'movement')
        display_account_labels = {
            'all': 'All Accounts',
            'movement': 'With Movements',
            'not_zero': 'Non-zero Balance',
        }
        sheet.merge_range('C8:G8', display_account_labels.get(
            display_account, 'With Movements'), filter_body)
        puc_labels = {
            '0': 'Full detail',
            '1': 'Class (1 digit)',
            '2': 'Group (2 digits)',
            '4': 'Account (4 digits)',
            '6': 'Subaccount (6 digits)',
        }
        puc_level = data['filters'].get('puc_level', '0')
        sheet.merge_range('C9:G9', puc_labels.get(str(puc_level), 'Full detail'),
                          filter_body)
        sheet.merge_range(
            'C10:G10', '%s to %s' % (
                data['filters'].get('account_from_code') or '...',
                data['filters'].get('account_to_code') or '...'), filter_body)
        sheet.merge_range(
            'C11:G11', '%s (%s)' % (
                data['filters'].get('analytics_label') or 'All',
                data['filters'].get('analytic_filter_label') or 'All lines'),
            filter_body)

        period_columns = data.get('period_columns') or [{
            'label': (data.get('date_viewed') or [''])[-1],
            'debitKey': 'total_debit',
            'creditKey': 'total_credit',
        }]
        col = 0
        sheet.merge_range(12, col, 13, col, 'Account', sub_heading)
        sheet.merge_range(12, col + 1, 13, col + 1, 'Initial Balance',
                          sub_heading)
        i = 2
        for period_column in period_columns:
            sheet.merge_range(
                12, col + i, 12, col + i + 1,
                period_column.get('label') or '', sub_heading)
            sheet.write(13, col + i, 'Debit', sub_heading)
            sheet.write(13, col + i + 1, 'Credit', sub_heading)
            i += 2
        sheet.merge_range(
            12, col + i, 12, col + i + 1, 'End Balance', sub_heading)
        sheet.write(13, col + i, 'Debit', sub_heading)
        sheet.write(13, col + i + 1, 'Credit', sub_heading)

        if data:
            if report_action == 'dynamic_accounts_report.action_trial_balance':
                row = 14
                for move_line in data['data'][0]:
                    sheet.write(row, col, move_line['account'],
                                side_heading_sub)
                    sheet.write(row, col + 1, move_line.get('initial', 0.0),
                                txt_name)
                    j = 2
                    for period_column in period_columns:
                        sheet.write(
                            row, col + j,
                            move_line.get(
                                period_column.get('debitKey'), 0.0), txt_name)
                        sheet.write(
                            row, col + j + 1,
                            move_line.get(
                                period_column.get('creditKey'), 0.0), txt_name)
                        j += 2
                    sheet.write(row, col + j,
                                move_line.get('final_debit', 0.0), txt_name)
                    sheet.write(row, col + j + 1,
                                move_line.get('final_credit', 0.0), txt_name)
                    row += 1
                totals = data.get('totals') or {}
                row += 1
                sheet.write(row, col, 'Total', side_heading_sub)
                sheet.write(row, col + 1, totals.get('initial', 0.0),
                            total_format)
                j = 2
                for period_column in period_columns:
                    sheet.write(row, col + j, totals.get(
                        period_column.get('debitKey'), 0.0), total_format)
                    sheet.write(row, col + j + 1, totals.get(
                        period_column.get('creditKey'), 0.0), total_format)
                    j += 2
                sheet.write(row, col + j, totals.get('final_debit', 0.0),
                            total_format)
                sheet.write(row, col + j + 1, totals.get('final_credit', 0.0),
                            total_format)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
