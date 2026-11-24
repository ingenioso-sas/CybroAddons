# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
################################################################################
import json
import logging
import urllib.request
from urllib.error import HTTPError, URLError

from odoo import api, fields, models, _
from odoo.tools import html_sanitize

_logger = logging.getLogger(__name__)

STATIC_SETTING = 'lm_studio.enable_static_audit'
AI_SETTING = 'lm_studio.enable_ai_audit'
AI_URL_SETTING = 'lm_studio.api_url'
AI_KEY_SETTING = 'lm_studio.api_key'
AI_MODEL_SETTING = 'lm_studio.model'

DEBIT_NORMAL_TYPES = {
    'asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current',
    'asset_prepayments', 'asset_fixed', 'expense', 'expense_depreciation',
    'expense_direct_cost',
}
CREDIT_NORMAL_TYPES = {
    'liability_payable', 'liability_credit_card', 'liability_current',
    'liability_non_current', 'equity', 'equity_unaffected', 'income',
    'income_other',
}


class AiFinancialAuditWizard(models.TransientModel):
    """Financial report audit using static accounting rules and/or an AI API."""
    _name = 'ai.financial.audit.wizard'
    _description = 'Financial Report Audit / Anomaly Panel'

    report_type = fields.Char(string='Report Type')
    active_model = fields.Char(string='Active Model')
    active_id = fields.Integer(string='Active ID')
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    journal_ids = fields.Many2many('account.journal', string='Journals')
    partner_ids = fields.Many2many('res.partner', string='Partners')
    account_ids = fields.Many2many('account.account', string='Accounts')
    audit_type = fields.Selection(
        selection='_get_audit_types', default='static',
        string='Analysis Type', required=True)
    is_ai_configured = fields.Boolean(
        compute='_compute_is_ai_configured', string='AI Configured')
    result_html = fields.Html(string='Analysis Result')

    # ------------------------------------------------------------------
    # Configuration / selection helpers
    # ------------------------------------------------------------------
    def _setting(self, key, default):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _static_enabled(self):
        return self._setting(STATIC_SETTING, 'True') == 'True'

    def _ai_enabled(self):
        return self._setting(AI_SETTING, 'False') == 'True'

    def _ai_config(self):
        return {
            'url': self._setting(AI_URL_SETTING, ''),
            'key': self._setting(AI_KEY_SETTING, ''),
            'model': self._setting(
                AI_MODEL_SETTING,
                'lmstudio-community/meta-llama-3-8b-instruct'),
        }

    def _get_audit_types(self):
        options = []
        if self._static_enabled():
            options.append((
                'static', _('Static Analysis (Accounting Rules)')))
        if self._ai_enabled():
            options.append(('ai', _('Intelligent AI Analysis')))
        if not options:
            options.append(('none', _('No analysis types enabled')))
        return options

    @api.depends('active_model', 'active_id')
    def _compute_is_ai_configured(self):
        config = self._ai_config()
        for record in self:
            record.is_ai_configured = bool(config['url'])

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        context = self.env.context
        static_enabled = self._static_enabled()
        ai_enabled = self._ai_enabled()
        if static_enabled:
            default_type = 'static'
        elif ai_enabled:
            default_type = 'ai'
        else:
            default_type = 'none'
        if default_type == 'none':
            init_html = _(
                "<div style='text-align:center;padding:30px;color:#d9534f;'>"
                "<h4>Sin análisis disponible</h4>"
                "<p>El administrador ha desactivado todos los tipos de "
                "análisis contables.</p></div>")
        else:
            init_html = _(
                "<div style='text-align:center;padding:30px;color:#666;'>"
                "<h4>Listo para analizar</h4>"
                "<p>Seleccione el tipo de análisis y haga clic en "
                "<strong>Ejecutar Análisis</strong>.</p></div>")
        date_from = context.get('date_from') or fields.Date.today().replace(
            month=1, day=1)
        date_to = context.get('date_to') or fields.Date.today()
        result.update({
            'report_type': context.get('report_type') or 'trial_balance',
            'active_model': context.get('active_model') or False,
            'active_id': context.get('active_id') or False,
            'date_from': fields.Date.to_date(date_from) or False,
            'date_to': fields.Date.to_date(date_to) or False,
            'journal_ids': [(6, 0, context.get('journal_ids') or [])],
            'partner_ids': [(6, 0, context.get('partner_ids') or [])],
            'account_ids': [(6, 0, context.get('account_ids') or [])],
            'audit_type': default_type,
            'result_html': init_html,
        })
        return result

    @api.onchange('audit_type')
    def _onchange_audit_type(self):
        if self.audit_type == 'ai' and not self._ai_config()['url']:
            self.audit_type = 'static'
            return {
                'warning': {
                    'title': _('Configuration Required'),
                    'message': _(
                        'Configure the AI server URL in the Dynamic Reports '
                        'audit settings before using the AI analysis.'),
                }
            }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_run_analysis(self):
        self.ensure_one()
        if self.audit_type == 'none':
            self.result_html = _(
                "<div style='text-align:center;padding:30px;color:#d9534f;'>"
                "<h4>Sin análisis disponible</h4>"
                "<p>No hay tipos de análisis habilitados.</p></div>")
        elif self.audit_type == 'static':
            self.result_html = self._run_static_audit()
        elif self.audit_type == 'ai':
            if not self._ai_config()['url']:
                self.result_html = _(
                    "<div style='padding:20px;color:#d9534f;'>"
                    "<h4>IA no configurada</h4>"
                    "<p>Configure la URL del servidor de IA en los ajustes de "
                    "la compañía.</p></div>")
            else:
                self.result_html = self._run_ai_audit()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.financial.audit.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': self.env.context,
        }

    # ------------------------------------------------------------------
    # Data extraction for Odoo 19
    # ------------------------------------------------------------------
    def _get_domain(self):
        domain = [('parent_state', '=', 'posted')]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        if self.account_ids:
            domain.append(('account_id', 'in', self.account_ids.ids))
        return domain

    def _period_label(self):
        if self.date_from and self.date_to:
            return '%s - %s' % (self.date_from, self.date_to)
        return str(self.date_from or self.date_to or '')

    def _get_account_rows(self):
        groups = self.env['account.move.line']._read_group(
            self._get_domain(), groupby=['account_id'],
            aggregates=['debit:sum', 'credit:sum'])
        rows = []
        for account, debit, credit in groups:
            debit = round(debit or 0.0, 2)
            credit = round(credit or 0.0, 2)
            rows.append({
                'account': account,
                'code': account.code or '',
                'name': account.name or '',
                'type': account.account_type or '',
                'debit': debit,
                'credit': credit,
                'balance': round(debit - credit, 2),
            })
        return sorted(rows, key=lambda row: (row['code'], row['name']))

    def _get_partner_rows(self, account_types, unreconciled=False):
        domain = self._get_domain()
        domain.append(('account_type', 'in', account_types))
        domain.append(('partner_id', '!=', False))
        if unreconciled:
            domain.append(('reconciled', '=', False))
        groups = self.env['account.move.line']._read_group(
            domain, groupby=['account_type', 'partner_id'],
            aggregates=['debit:sum', 'credit:sum'])
        rows = []
        for account_type, partner, debit, credit in groups:
            debit = round(debit or 0.0, 2)
            credit = round(credit or 0.0, 2)
            rows.append({
                'partner': partner,
                'account_type': account_type,
                'debit': debit,
                'credit': credit,
                'balance': round(debit - credit, 2),
            })
        return rows

    def _get_type_totals(self, rows):
        totals = {}
        for row in rows:
            account_type = row['type']
            if account_type.startswith('asset_'):
                totals['assets'] = totals.get('assets', 0.0) + row['balance']
            elif account_type.startswith('liability_'):
                totals['liabilities'] = (
                    totals.get('liabilities', 0.0) - row['balance'])
            elif account_type.startswith('equity'):
                totals['equity'] = totals.get('equity', 0.0) - row['balance']
            elif account_type.startswith('income'):
                totals['income'] = totals.get('income', 0.0) - row['balance']
            elif account_type.startswith('expense'):
                totals['expenses'] = (
                    totals.get('expenses', 0.0) + row['balance'])
        return {key: round(value, 2) for key, value in totals.items()}

    # ------------------------------------------------------------------
    # Static audit
    # ------------------------------------------------------------------
    def _run_static_audit(self):
        try:
            report_type = self.report_type or 'trial_balance'
            if report_type in ('trial_balance', 'general_ledger'):
                anomalies = self._audit_account_nature()
            elif report_type in ('partner_ledger', 'aged_payable',
                                 'aged_receivable', 'partner_ageing'):
                anomalies = self._audit_partner_balances(report_type)
            elif report_type in ('balance_sheet', 'profit_loss'):
                anomalies = self._audit_financial_statement(report_type)
            else:
                anomalies = [{
                    'type': 'warning',
                    'title': _('Unsupported report'),
                    'desc': _('The report type "%s" has no static rules.') %
                            report_type,
                    'explanation': _(
                        'This report does not have a static audit profile.'),
                    'solution': _(
                        'Use the AI analysis or contact technical support to '
                        'add specific accounting rules.'),
                }]
        except Exception as error:
            _logger.exception('Error during static financial audit')
            return _(
                "<h3>Error al realizar la auditoría</h3><p>%s</p>") % str(error)
        return self._generate_html_report(anomalies)

    def _audit_account_nature(self):
        rows = self._get_account_rows()
        anomalies = []
        total_debit = round(sum(row['debit'] for row in rows), 2)
        total_credit = round(sum(row['credit'] for row in rows), 2)
        if abs(total_debit - total_credit) > 0.01:
            anomalies.append({
                'type': 'critical',
                'title': _('Trial Balance is out of balance'),
                'desc': _(
                    'Total debits (%.2f) do not match total credits (%.2f).') %
                        (total_debit, total_credit),
                'explanation': _(
                    'The double-entry principle is broken. Every journal entry '
                    'must have equal debit and credit amounts.'),
                'solution': _(
                    'Review posted journal entries for rounding differences or '
                    'import errors.'),
            })
        for row in rows:
            account_type = row['type']
            balance = row['balance']
            if account_type in DEBIT_NORMAL_TYPES and balance < -0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Unusual credit balance: %s (%s)') % (
                        row['name'], row['code']),
                    'desc': _(
                        'The account has a credit balance of %.2f '
                        '(Debit %.2f / Credit %.2f).') % (
                            abs(balance), row['debit'], row['credit']),
                    'explanation': _(
                        'Asset and expense accounts normally have debit '
                        'balances. A credit balance can indicate an overdraft '
                        'or entries recorded in the wrong direction.'),
                    'solution': _(
                        'Reconcile cash/bank accounts and review the account '
                        'movements for the period.'),
                })
            elif account_type in CREDIT_NORMAL_TYPES and balance > 0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Unusual debit balance: %s (%s)') % (
                        row['name'], row['code']),
                    'desc': _(
                        'The account has a debit balance of %.2f '
                        '(Debit %.2f / Credit %.2f).') % (
                            balance, row['debit'], row['credit']),
                    'explanation': _(
                        'Liability, equity and income accounts normally have '
                        'credit balances. A debit balance can indicate an '
                        'overpayment or an incorrect reversal.'),
                    'solution': _(
                        'Review vendor bills, customer payments and adjustment '
                        'entries related to this account.'),
                })
        return anomalies

    def _audit_partner_balances(self, report_type):
        anomalies = []
        account_types = ['asset_receivable', 'liability_payable']
        unreconciled = report_type in (
            'aged_payable', 'aged_receivable', 'partner_ageing')
        for row in self._get_partner_rows(account_types, unreconciled):
            balance = row['balance']
            partner_name = row['partner'].display_name
            if row['account_type'] == 'asset_receivable' and balance < -0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Customer with credit balance: %s') % partner_name,
                    'desc': _(
                        'The customer has a credit balance of %.2f.') %
                            abs(balance),
                    'explanation': _(
                        'The customer paid more than the invoiced amount or has '
                        'an unapplied advance.'),
                    'solution': _(
                        'Reconcile pending payments with invoices or apply the '
                        'advance to a future invoice.'),
                })
            elif row['account_type'] == 'liability_payable' and balance > 0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Vendor with debit balance: %s') % partner_name,
                    'desc': _(
                        'The vendor has a debit balance of %.2f.') % balance,
                    'explanation': _(
                        'The vendor was paid more than the billed amount or has '
                        'an unapplied advance.'),
                    'solution': _(
                        'Reconcile vendor payments with bills or apply the '
                        'advance to a pending bill.'),
                })
        return anomalies

    def _audit_financial_statement(self, report_type):
        rows = self._get_account_rows()
        totals = self._get_type_totals(rows)
        anomalies = []
        if report_type == 'balance_sheet':
            assets = totals.get('assets', 0.0)
            liabilities = totals.get('liabilities', 0.0)
            equity = totals.get('equity', 0.0)
            income = totals.get('income', 0.0)
            expenses = totals.get('expenses', 0.0)
            difference = abs(assets - (liabilities + equity +
                                       income - expenses))
            if difference > 1.0:
                anomalies.append({
                    'type': 'critical',
                    'title': _('Accounting equation is out of balance'),
                    'desc': _(
                        'Assets (%.2f) do not match Liabilities + Equity + '
                        'Result (%.2f). Difference: %.2f') % (
                            assets, liabilities + equity + income - expenses,
                            difference),
                    'explanation': _(
                        'The balance sheet is not balanced. This can be caused '
                        'by an incorrect account type or orphan accounts.'),
                    'solution': _(
                        'Review the chart of accounts and the account types of '
                        'all accounts.'),
                })
        return anomalies

    def _generate_html_report(self, anomalies):
        html = """
        <div style="font-family: Arial, sans-serif; padding: 15px;">
            <div style="background-color: #f8f9fa; border-left: 5px solid #00A0AD; padding: 10px; margin-bottom: 20px; border-radius: 4px;">
                <h4 style="margin: 0; color: #00A0AD;">Panel de Auditoría Contable (Reglas Estáticas)</h4>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #6c757d;">
                    Análisis de partida doble, naturaleza de saldos e integridad de cuentas para el periodo seleccionado.
                </p>
            </div>
        """
        if not anomalies:
            html += """
            <div style="background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 15px; border-radius: 4px; text-align: center;">
                <h4 style="margin-top: 0;">No se encontraron anomalías críticas</h4>
                <p style="margin-bottom: 0; font-size: 14px;">
                    Las cifras cumplen con las reglas básicas de coherencia y partida doble.
                </p>
            </div>
            """
        else:
            html += "<h5>Anomalías y advertencias detectadas:</h5>"
            for anomaly in anomalies:
                is_critical = anomaly.get('type') == 'critical'
                color = '#dc3545' if is_critical else '#ffc107'
                bg_color = '#f8d7da' if is_critical else '#fff3cd'
                border_color = '#f5c6cb' if is_critical else '#ffeeba'
                badge = 'Crítico' if is_critical else 'Advertencia'
                html += """
                <div style="background-color: %s; border: 1px solid %s; border-left: 5px solid %s; padding: 15px; border-radius: 4px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <strong style="font-size: 15px; color: #333;">%s</strong>
                        <span style="background-color: %s; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">%s</span>
                    </div>
                    <p style="margin: 5px 0; font-size: 13.5px; font-weight: bold; color: #333;">Detalle: %s</p>
                    <p style="margin: 5px 0; font-size: 13px; color: #555;"><strong>Explicación:</strong> %s</p>
                    <p style="margin: 5px 0; font-size: 13px; color: #222; background-color: #ffffff; padding: 8px; border-radius: 4px; border: 1px dashed #ccc;">
                        <strong>Acción de corrección:</strong> %s
                    </p>
                </div>
                """ % (
                    bg_color, border_color, color, anomaly.get('title', ''),
                    color, badge, anomaly.get('desc', ''),
                    anomaly.get('explanation', ''), anomaly.get('solution', ''))
        return html + "</div>"

    # ------------------------------------------------------------------
    # AI audit
    # ------------------------------------------------------------------
    def _run_ai_audit(self):
        try:
            summary = self._get_ai_summary()
        except Exception as error:
            _logger.exception('Error preparing data for the AI audit')
            return _("<p>Error al preparar los datos para la IA: %s</p>") % str(error)
        return self._call_ai(summary)

    def _get_ai_summary(self):
        report_type = self.report_type or 'trial_balance'
        label = self._period_label()
        if report_type in ('partner_ledger', 'aged_payable',
                           'aged_receivable', 'partner_ageing'):
            rows = self._get_partner_rows(
                ['asset_receivable', 'liability_payable'],
                report_type != 'partner_ledger')
            summary = 'Reporte: %s\nPeriodo: %s\n\nSaldos por tercero:\n' % (
                report_type, label)
            for row in rows[:200]:
                summary += '- %s (%s): Debito=%.2f, Credito=%.2f, Saldo=%.2f\n' % (
                    row['partner'].display_name, row['account_type'],
                    row['debit'], row['credit'], row['balance'])
            return summary
        rows = self._get_account_rows()
        totals = self._get_type_totals(rows)
        if report_type in ('balance_sheet', 'profit_loss'):
            return (
                'Reporte: %s\nPeriodo: %s\nActivos: %.2f\nPasivos: %.2f\n'
                'Patrimonio: %.2f\nIngresos: %.2f\nGastos: %.2f\n' % (
                    report_type, label, totals.get('assets', 0.0),
                    totals.get('liabilities', 0.0), totals.get('equity', 0.0),
                    totals.get('income', 0.0), totals.get('expenses', 0.0)))
        total_debit = round(sum(row['debit'] for row in rows), 2)
        total_credit = round(sum(row['credit'] for row in rows), 2)
        summary = (
            'Reporte: %s\nPeriodo: %s\nTotal debitos: %.2f\n'
            'Total creditos: %.2f\n\nSaldos por cuenta:\n' % (
                report_type, label, total_debit, total_credit))
        for row in rows[:200]:
            summary += '- %s %s: Debito=%.2f, Credito=%.2f, Saldo=%.2f\n' % (
                row['code'], row['name'], row['debit'], row['credit'],
                row['balance'])
        return summary

    def _call_ai(self, data_summary):
        config = self._ai_config()
        url = (config['url'] or '').strip()
        if not url:
            return _("<p>Error: la URL del servidor de IA no está configurada.</p>")
        if not url.endswith('/chat/completions'):
            url = url.rstrip('/')
            if not url.endswith('/v1'):
                url += '/v1'
            url += '/chat/completions'
        model = config['model'] or 'lmstudio-community/meta-llama-3-8b-instruct'
        prompt = """
        Actúa como un Auditor Contable y Financiero profesional. Analiza el
        siguiente reporte financiero de Odoo (Tipo: %s, Periodo: %s):

        %s

        Identifica descuadres contables, saldos invertidos o inusuales y
        discrepancias. Presenta el resultado en HTML limpio para mostrarlo en
        Odoo. Incluye estas secciones:
        1. Resumen ejecutivo
        2. Hallazgos y anomalías clave
        3. Explicación contable
        4. Acciones sugeridas

        Responde únicamente con HTML, sin marcas markdown.
        """ % (self.report_type, self._period_label(), data_summary)
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': (
                    'Eres un auditor financiero experto. Respondes únicamente '
                    'con HTML válido, sin marcas markdown.')},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
        }
        try:
            request = urllib.request.Request(
                url, data=json.dumps(payload).encode('utf-8'), method='POST')
            request.add_header('Content-Type', 'application/json')
            if config['key']:
                request.add_header(
                    'Authorization', 'Bearer %s' % config['key'])
            with urllib.request.urlopen(request, timeout=60) as response:
                response_data = json.loads(
                    response.read().decode('utf-8'))
            choices = response_data.get('choices', [])
            if not choices:
                return _(
                    "<p>Error: el servidor de IA no devolvió una respuesta.</p>")
            content = choices[0].get('message', {}).get('content', '')
            return html_sanitize(content.strip())
        except HTTPError as error:
            _logger.exception('AI audit HTTP error')
            try:
                body = error.read().decode('utf-8')
                detail = json.loads(body).get('error', {}).get(
                    'message', body)
            except Exception:
                detail = str(error)
            return _(
                "<p>Error HTTP del servidor de IA (%s): %s</p>") % (
                    error.code, detail)
        except URLError as error:
            _logger.exception('AI audit connection error')
            return _(
                "<p>No se pudo conectar con el servidor de IA en %s: %s</p>") % (
                    url, error.reason)
        except Exception as error:
            _logger.exception('AI audit unexpected error')
            return _(
                "<p>Error inesperado durante el análisis con IA: %s</p>") % str(
                    error)
