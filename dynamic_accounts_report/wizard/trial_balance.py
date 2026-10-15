import time
from odoo import fields, models, api, _

import io
import json
from odoo.http import request
from odoo.exceptions import AccessError, UserError, AccessDenied

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class TrialView(models.TransientModel):
    _inherit = "account.common.report"
    _name = 'account.trial.balance'

    journal_ids = fields.Many2many('account.journal',

                                   string='Journals', required=True,
                                   default=[])
    display_account = fields.Selection(
        [('all', 'All'), ('movement', 'With movements'),
         ('not_zero', 'With balance is not equal to 0')],
        string='Display Accounts', required=True, default='movement')
    puc_level = fields.Selection(
        [('0', 'Detalle completo'),
         ('1', 'Clase (1 dígito)'),
         ('2', 'Grupo (2 dígitos)'),
         ('4', 'Cuenta (4 dígitos)'),
         ('6', 'Subcuenta (6 dígitos)')],
        string='Nivel PUC', default='0', required=True,
        help='Nivel de desagregación del PUC Colombia. Los saldos de las '
             'subcuentas se consolidan por el prefijo del código.')
    account_from_code = fields.Char(
        string='Cuenta desde',
        help='Código PUC inicial del rango (inclusivo). Vacío = desde la '
             'primera.')
    account_to_code = fields.Char(
        string='Cuenta hasta',
        help='Código PUC final del rango (inclusivo). Vacío = hasta la '
             'última.')

    @api.model
    def view_report(self, option):
        r = self.env['account.trial.balance'].search([('id', '=', option[0])])

        data = {
            'display_account': r.display_account,
            'model':self,
            'journals': r.journal_ids,
            'target_move': r.target_move,
            'puc_level': r.puc_level or '0',
            'account_from_code': (r.account_from_code or '').strip(),
            'account_to_code': (r.account_to_code or '').strip(),

        }
        if r.date_from:
            data.update({
                'date_from':r.date_from,
            })
        if r.date_to:
            data.update({
                'date_to':r.date_to,
            })

        filters = self.get_filter(option)
        records = self._get_report_values(data)
        currency = self._get_currency()

        return {
            'name': "Trial Balance",
            'type': 'ir.actions.client',
            'tag': 't_b',
            'filters': filters,
            'report_lines': records['Accounts'],
            'debit_total': records['debit_total'],
            'credit_total': records['credit_total'],
            'initial_total': records.get('initial_total', 0.0),
            'final_debit_total': records.get('final_debit_total', 0.0),
            'final_credit_total': records.get('final_credit_total', 0.0),
            'currency': currency,
        }

    def get_filter(self, option):
        data = self.get_filter_data(option)
        filters = {}
        if data.get('journal_ids'):
            filters['journals'] = self.env['account.journal'].browse(data.get('journal_ids')).mapped('code')
        else:
            filters['journals'] = ['All']
        if data.get('target_move'):
            filters['target_move'] = data.get('target_move')
        if data.get('date_from'):
            filters['date_from'] = data.get('date_from')
        if data.get('date_to'):
            filters['date_to'] = data.get('date_to')

        filters['company_id'] = ''
        filters['journals_list'] = data.get('journals_list')
        filters['company_name'] = data.get('company_name')
        filters['target_move'] = data.get('target_move').capitalize()
        filters['puc_level'] = data.get('puc_level', '0')
        level_labels = {'0': 'Detalle completo', '1': 'Clase (1)',
                        '2': 'Grupo (2)', '4': 'Cuenta (4)',
                        '6': 'Subcuenta (6)'}
        filters['puc_level_label'] = level_labels.get(
            str(data.get('puc_level', '0')), '')
        filters['account_from_code'] = data.get('account_from_code', '')
        filters['account_to_code'] = data.get('account_to_code', '')

        enable_static = self.env['ir.config_parameter'].sudo().get_param('dynamic_accounts_report.enable_static_audit', 'False') == 'True'
        enable_ai = self.env['ir.config_parameter'].sudo().get_param('dynamic_accounts_report.enable_ai_audit', 'False') == 'True'
        filters['enable_audit_button'] = enable_static or enable_ai
        return filters

    def get_current_company_value(self):

        cookies_cids = [int(r) for r in request.httprequest.cookies.get('cids').split(",")] \
            if request.httprequest.cookies.get('cids') \
            else [request.env.user.company_id.id]
        for company_id in cookies_cids:
            if company_id not in self.env.user.company_ids.ids:
                cookies_cids.remove(company_id)
        if not cookies_cids:
            cookies_cids = [self.env.company.id]
        if len(cookies_cids) == 1:
            cookies_cids.append(0)
        return cookies_cids

    def get_filter_data(self, option):
        r = self.env['account.trial.balance'].search([('id', '=', option[0])])
        default_filters = {}
        company_id = self.env.companies.ids
        company_domain = [('company_id', 'in', company_id)]
        journal_ids = r.journal_ids if r.journal_ids else self.env['account.journal'].search(company_domain, order="company_id, name")


        journals = []
        o_company = False
        for j in journal_ids:
            if j.company_id != o_company:
                journals.append(('divider', j.company_id.name))
                o_company = j.company_id
            journals.append((j.id, j.name, j.code))

        filter_dict = {
            'journal_ids': r.journal_ids.ids,
            'company_id': company_id,
            'date_from': r.date_from,
            'date_to': r.date_to,
            'target_move': r.target_move,
            'journals_list': journals,
            # 'journals_list': [(j.id, j.name, j.code) for j in journals],

            'company_name': ', '.join(self.env.companies.mapped('name')),
            'puc_level': r.puc_level or '0',
            'account_from_code': (r.account_from_code or '').strip(),
            'account_to_code': (r.account_to_code or '').strip(),
        }
        filter_dict.update(default_filters)
        return filter_dict

    def _get_report_values(self, data):
        docs = data['model']
        display_account = data['display_account']
        journals = data['journals']
        accounts = self.env['account.account'].search([])
        if not accounts:
            raise UserError(_("No Accounts Found! Please Add One"))
        account_res = self._get_accounts(accounts, display_account, data)
        debit_total = sum(x['debit'] for x in account_res)
        credit_total = sum(x['credit'] for x in account_res)
        initial_total = sum(x.get('initial', 0.0) for x in account_res)
        final_debit_total = sum(
            x.get('final_debit', 0.0) for x in account_res)
        final_credit_total = sum(
            x.get('final_credit', 0.0) for x in account_res)
        return {
            'doc_ids': self.ids,
            'debit_total': debit_total,
            'credit_total': credit_total,
            'initial_total': initial_total,
            'final_debit_total': final_debit_total,
            'final_credit_total': final_credit_total,
            'docs': docs,
            'time': time,
            'Accounts': account_res,
        }

    @api.model
    def create(self, vals):
        vals['target_move'] = 'posted'
        res = super(TrialView, self).create(vals)
        return res

    def write(self, vals):
        if vals.get('target_move'):
            vals.update({'target_move': vals.get('target_move').lower()})
        if vals.get('journal_ids'):
            vals.update({'journal_ids': [(6, 0, vals.get('journal_ids'))]})
        if vals.get('journal_ids') == []:
            vals.update({'journal_ids': [(5,)]})
        res = super(TrialView, self).write(vals)
        return res

    def _get_sums(self, accounts, data, initial=False):
        """Una sola query agrupada: {account_id: {debit, credit}}.

        Si initial=True, acumula lo anterior a date_from (saldo anterior).
        Parametrizado (sin interpolación de fechas en el SQL).
        """
        if not accounts:
            return {}
        tables, where_clause, where_params = self.env[
            'account.move.line']._query_get()
        tables = (tables or 'account_move_line').replace('"', '')
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        base_filter = " AND ".join(wheres)
        target = (data.get('target_move') or 'posted').lower()
        extra = ""
        params_extra = []
        if target == 'posted':
            extra += " AND account_move_line.parent_state = 'posted'"
        else:
            extra += (" AND account_move_line.parent_state in "
                      "('draft','posted')")
        if initial:
            if data.get('date_from'):
                extra += " AND account_move_line.date < %s"
                params_extra.append(data.get('date_from'))
            else:
                return {}
        else:
            if data.get('date_from'):
                extra += " AND account_move_line.date >= %s"
                params_extra.append(data.get('date_from'))
            if data.get('date_to'):
                extra += " AND account_move_line.date <= %s"
                params_extra.append(data.get('date_to'))
        journals = data.get('journals')
        journal_ids = journals.ids if journals else []
        if journal_ids:
            extra += " AND account_move_line.journal_id IN %s"
            params_extra.append(tuple(journal_ids))
        request = (
            "SELECT account_id AS id, COALESCE(SUM(debit), 0.0) AS debit, "
            "COALESCE(SUM(credit), 0.0) AS credit, "
            "(COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0)) AS balance"
            " FROM " + tables + " WHERE account_id IN %s " + base_filter +
            extra + " GROUP BY account_id")
        params = ((tuple(accounts.ids),) + tuple(where_params or ()) +
                  tuple(params_extra))
        self.env.cr.execute(request, params)
        return {row.pop('id'): row for row in self.env.cr.dictfetchall()}

    def _get_accounts(self, accounts, display_account, data):

        # Filtro por rango de códigos PUC (antes de consultar)
        code_from = (data.get('account_from_code') or '').strip()
        code_to = (data.get('account_to_code') or '').strip()
        if code_from or code_to:
            def _in_range(acc):
                code = (acc.code or '').strip()
                if code_from and code < code_from:
                    return False
                if code_to and code > code_to:
                    return False
                return True
            accounts = accounts.filtered(_in_range)
        try:
            level = int(data.get('puc_level') or 0)
        except (TypeError, ValueError):
            level = 0

        # 2 queries masivas (periodo + saldo anterior), sin N+1
        period_sums = self._get_sums(accounts, data, initial=False)
        init_sums = self._get_sums(accounts, data, initial=True)

        detail = []
        for account in accounts.sorted(key=lambda a: (a.code or '', a.id)):
            per = period_sums.get(
                account.id, {'debit': 0.0, 'credit': 0.0, 'balance': 0.0})
            ini = init_sums.get(
                account.id, {'debit': 0.0, 'credit': 0.0, 'balance': 0.0})
            initial = (ini.get('balance') if data.get('date_from')
                       else 0.0) or 0.0
            debit = per.get('debit', 0.0) or 0.0
            credit = per.get('credit', 0.0) or 0.0
            balance = initial + debit - credit
            detail.append({
                'code': (account.code or '').strip(),
                'name': account.name,
                'id': account.id,
                'initial': initial,
                'Init_balance': {'debit': ini.get('debit', 0.0) or 0.0,
                                 'credit': ini.get('credit', 0.0) or 0.0,
                                 'balance': initial},
                'debit': debit,
                'credit': credit,
                'balance': balance,
            })

        # Consolidación por nivel PUC (las hijas se suman en el prefijo)
        if level > 0:
            by_code = {a.code: (a.name, a.id) for a in accounts}
            grouped = {}
            for line in detail:
                prefix = line['code'][:level] or line['code']
                if prefix not in grouped:
                    pname, pid = by_code.get(prefix, (prefix + ' (grupo)',
                                                      False))
                    grouped[prefix] = {
                        'code': prefix, 'name': pname, 'id': pid,
                        'initial': 0.0,
                        'Init_balance': {'debit': 0.0, 'credit': 0.0,
                                         'balance': 0.0},
                        'debit': 0.0, 'credit': 0.0, 'balance': 0.0,
                    }
                g = grouped[prefix]
                g['initial'] += line['initial']
                g['Init_balance']['debit'] += line['Init_balance']['debit']
                g['Init_balance']['credit'] += line['Init_balance']['credit']
                g['Init_balance']['balance'] += line['initial']
                g['debit'] += line['debit']
                g['credit'] += line['credit']
                g['balance'] += line['balance']
            detail = sorted(grouped.values(), key=lambda r: r['code'])

        account_res = []
        for res in detail:
            balance = res['balance']
            currency = self.env.company.currency_id
            res['final_debit'] = balance if balance > 0 else 0.0
            res['final_credit'] = -balance if balance < 0 else 0.0
            if display_account == 'all':
                account_res.append(res)
            elif display_account == 'not_zero' and not currency.is_zero(
                    balance):
                account_res.append(res)
            elif display_account == 'movement' and (
                    not currency.is_zero(res['debit']) or not currency.is_zero(
                        res['credit']) or
                    (data.get('date_from') and not currency.is_zero(
                        res['initial']))):
                account_res.append(res)
        return account_res

    def get_init_bal(self, account, display_account, data):
        if data.get('date_from'):

            tables, where_clause, where_params = self.env[
                'account.move.line']._query_get()
            tables = tables.replace('"', '')
            if not tables:
                tables = 'account_move_line'
            wheres = [""]
            if where_clause.strip():
                wheres.append(where_clause.strip())
            filters = " AND ".join(wheres)
            if data['target_move'] == 'posted':
                filters += " AND account_move_line.parent_state = 'posted'"
            else:
                filters += " AND account_move_line.parent_state in ('draft','posted')"
            if data.get('date_from'):
                filters += " AND account_move_line.date < '%s'" % data.get('date_from')

            if data['journals']:
                filters += ' AND jrnl.id IN %s' % str(tuple(data['journals'].ids) + tuple([0]))
            tables += ' JOIN account_journal jrnl ON (account_move_line.journal_id=jrnl.id)'

            # compute the balance, debit and credit for the provided accounts
            request = (
                    "SELECT account_id AS id, SUM(debit) AS debit, SUM(credit) AS credit, (SUM(debit) - SUM(credit)) AS balance" + \
                    " FROM " + tables + " WHERE account_id = %s" % account.id + filters + " GROUP BY account_id")
            params = tuple(where_params)
            self.env.cr.execute(request, params)
            for row in self.env.cr.dictfetchall():
                return row

    @api.model
    def _get_currency(self):
        journal = self.env['account.journal'].browse(
            self.env.context.get('default_journal_id', False))
        if journal.currency_id:
            return journal.currency_id.id
        lang = self.env.user.lang
        if not lang:
            lang = 'en_US'
        lang = lang.replace("_", '-')
        currency_array = [self.env.company.currency_id.symbol,
                          self.env.company.currency_id.position,
                          lang]
        return currency_array

    def get_dynamic_xlsx_report(self, data, response ,report_data, dfr_data):
        report_data_main = json.loads(report_data)
        output = io.BytesIO()
        total = json.loads(dfr_data)
        filters = json.loads(data)
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet()
        head = workbook.add_format({'align': 'center', 'bold': True,
                                    'font_size': '20px'})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1,
             'border_color': 'black'})
        txt = workbook.add_format({'font_size': '10px', 'border': 1})
        txt_l = workbook.add_format({'font_size': '10px', 'border': 1, 'bold': True})
        sheet.merge_range('A2:G3', filters.get('company_name') + ':' + ' Balance de Comprobación', head)
        date_head = workbook.add_format({'align': 'center', 'bold': True,
                                         'font_size': '10px'})
        date_style = workbook.add_format({'align': 'center',
                                          'font_size': '10px'})
        if filters.get('date_from'):
            sheet.merge_range('A4:C4', 'Desde: '+filters.get('date_from') , date_head)
        if filters.get('date_to'):
            sheet.merge_range('D4:G4', 'Hasta: '+ filters.get('date_to'), date_head)
        level_labels = {'0': 'Detalle completo', '1': 'Clase (1)',
                        '2': 'Grupo (2)', '4': 'Cuenta (4)',
                        '6': 'Subcuenta (6)'}
        sheet.merge_range(
            'A5:G5', 'Nivel PUC: %s   Rango: %s a %s' % (
                level_labels.get(str(filters.get('puc_level', '0')), ''),
                filters.get('account_from_code') or '...',
                filters.get('account_to_code') or '...'), date_head)
        sheet.merge_range('A6:G6', 'Diarios: ' + ', '.join([ lt or '' for lt in filters['journals'] ]) + '  Asientos: '+ filters.get('target_move'), date_head)
        sheet.write('A7', 'Código', sub_heading)
        sheet.write('B7', 'Cuenta (PUC/NIIF)', sub_heading)
        sheet.write('C7', 'Saldo Anterior', sub_heading)
        sheet.write('D7', 'Débito', sub_heading)
        sheet.write('E7', 'Crédito', sub_heading)
        sheet.write('F7', 'Saldo Final Deudor', sub_heading)
        sheet.write('G7', 'Saldo Final Acreedor', sub_heading)

        row = 6
        col = 0
        sheet.set_column(0, 0, 15)
        sheet.set_column(1, 1, 40)
        sheet.set_column(2, 6, 18)
        for rec_data in report_data_main:

            row += 1
            sheet.write(row, col, rec_data['code'], txt)
            sheet.write(row, col + 1, rec_data['name'], txt)
            sheet.write(row, col + 2, rec_data.get('initial', 0.0), txt)
            sheet.write(row, col + 3, rec_data['debit'], txt)
            sheet.write(row, col + 4, rec_data['credit'], txt)
            sheet.write(row, col + 5, rec_data.get('final_debit', 0.0), txt)
            sheet.write(row, col + 6, rec_data.get('final_credit', 0.0), txt)
        sheet.write(row+1, col, 'TOTALES', sub_heading)
        sheet.write(row + 1, col + 1, '', sub_heading)
        sheet.write(row + 1, col + 2, total.get('initial_total', 0.0), txt_l)
        sheet.write(row + 1, col + 3, total.get('debit_total'), txt_l)
        sheet.write(row + 1, col + 4, total.get('credit_total'), txt_l)
        sheet.write(row + 1, col + 5, total.get('final_debit_total', 0.0),
                    txt_l)
        sheet.write(row + 1, col + 6, total.get('final_credit_total', 0.0),
                    txt_l)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
