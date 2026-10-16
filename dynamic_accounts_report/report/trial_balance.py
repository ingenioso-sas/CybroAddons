from odoo import api, models, _


class TrialBalance(models.AbstractModel):
    _name = 'report.dynamic_accounts_report.trial_balance'

    @api.model
    def _get_report_values(self, docids, data=None):
        if self.env.context.get('trial_pdf_report'):

            if data.get('report_data'):
                report_data = data.get('report_data')
                data.update({'account_data': report_data['report_lines'],
                             'Filters': dict(
                                 report_data['filters'],
                                 initial_total=report_data.get(
                                     'initial_total', 0.0),
                                 final_debit_total=report_data.get(
                                     'final_debit_total', 0.0),
                                 final_credit_total=report_data.get(
                                     'final_credit_total', 0.0)),
                             'debit_total': report_data['debit_total'],
                             'credit_total': report_data['credit_total'],
                             'company': self.env.company,
                             })
        return data
