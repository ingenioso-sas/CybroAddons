# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import urllib.request
from urllib.error import URLError

_logger = logging.getLogger(__name__)

class AiFinancialAuditWizard(models.TransientModel):
    _name = 'ai.financial.audit.wizard'
    _description = 'Auditoría Financiera y Panel de Anomalías'

    report_type = fields.Char(string='Report Type')
    active_model = fields.Char(string='Active Model')
    active_id = fields.Integer(string='Active ID')
    audit_type = fields.Selection(selection='_get_audit_types', default='static', string='Tipo de Análisis', required=True)
    
    is_ai_configured = fields.Boolean(compute='_compute_is_ai_configured', string='IA Configurada')
    result_html = fields.Html(string='Resultado del Análisis')

    def _get_audit_types(self):
        options = []
        enable_static = self.env['ir.config_parameter'].sudo().get_param('lm_studio.enable_static_audit', 'True') == 'True'
        enable_ai = self.env['ir.config_parameter'].sudo().get_param('lm_studio.enable_ai_audit', 'True') == 'True'
        
        if enable_static:
            options.append(('static', _('Análisis Estático (Reglas Contables)')))
        if enable_ai:
            options.append(('ai', _('Análisis Inteligente con IA')))
            
        if not options:
            options.append(('none', _('No hay tipos de análisis habilitados')))
        return options

    @api.model
    def default_get(self, fields_list):
        res = super(AiFinancialAuditWizard, self).default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        report_type = self.env.context.get('report_type')

        enable_static = self.env['ir.config_parameter'].sudo().get_param('lm_studio.enable_static_audit', 'True') == 'True'
        enable_ai = self.env['ir.config_parameter'].sudo().get_param('lm_studio.enable_ai_audit', 'True') == 'True'
        
        default_type = 'static'
        if not enable_static:
            default_type = 'ai' if enable_ai else 'none'

        if default_type == 'none':
            init_html = _("<div style='text-align: center; padding: 30px; color: #d9534f;'>"
                          "<h4>⚠️ Sin análisis disponible</h4>"
                          "<p>El administrador ha desactivado todos los tipos de análisis contables.</p>"
                          "</div>")
        else:
            init_html = _("<div style='text-align: center; padding: 30px; color: #666;'>"
                             "<h4>📋 Listo para Analizar</h4>"
                             "<p>Seleccione el tipo de análisis y haga clic en <strong>\"Ejecutar Análisis\"</strong> en el pie de página para comenzar.</p>"
                             "</div>")

        res.update({
            'active_model': active_model,
            'active_id': active_id,
            'report_type': report_type,
            'audit_type': default_type,
            'result_html': init_html
        })
        return res

    @api.depends('active_model', 'active_id')
    def _compute_is_ai_configured(self):
        url = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_url')
        key = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_key')
        for rec in self:
            rec.is_ai_configured = bool(url and key)

    @api.constrains('audit_type')
    def _check_audit_type_config(self):
        for rec in self:
            if rec.audit_type == 'ai':
                url = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_url')
                key = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_key')
                if not url or not key:
                    raise UserError(_("No se puede habilitar el Análisis con IA. Configure los parámetros de sistema 'lm_studio.api_url' y 'lm_studio.api_key' en Odoo."))

    @api.onchange('audit_type')
    def _onchange_audit_type(self):
        if self.audit_type == 'ai':
            url = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_url')
            key = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_key')
            if not url or not key:
                self.audit_type = 'static'
                return {
                    'warning': {
                        'title': _("Configuración Requerida"),
                        'message': _("No se puede habilitar el Análisis con IA. Por favor, configure los parámetros 'lm_studio.api_url' y 'lm_studio.api_key' en los parámetros del sistema."),
                    }
                }

    def action_run_analysis(self):
        self.ensure_one()
        wizard_record = self.env[self.active_model].browse(self.active_id)
        if not wizard_record.exists():
            raise UserError(_("No se encontró el reporte activo."))

        if self.audit_type == 'none':
            self.result_html = _("<div style='text-align: center; padding: 30px; color: #d9534f;'>"
                                 "<h4>⚠️ Sin análisis disponible</h4>"
                                 "<p>El administrador ha desactivado todos los tipos de análisis contables.</p>"
                                 "</div>")
        elif self.audit_type == 'static':
            self.result_html = self._run_static_audit(wizard_record, self.report_type)
        elif self.audit_type == 'ai':
            self.result_html = self._run_ai_audit(wizard_record, self.report_type)

        # Return action to reload the wizard with the generated html result
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.financial.audit.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': self.env.context,
        }

    def _run_static_audit(self, wizard, report_type):
        anomalies = []
        try:
            if report_type == 'trial_balance':
                anomalies = self._audit_trial_balance(wizard)
            elif report_type == 'general_ledger':
                anomalies = self._audit_general_ledger(wizard)
            elif report_type == 'partner_ledger':
                anomalies = self._audit_partner_ledger(wizard)
            elif report_type == 'partner_ageing':
                anomalies = self._audit_partner_ageing(wizard)
            elif report_type in ('balance_sheet', 'profit_loss'):
                anomalies = self._audit_financial_reports(wizard, report_type)
            else:
                anomalies = [{
                    'type': 'warning',
                    'title': _('Reporte no soportado'),
                    'desc': _('El tipo de reporte "%s" no tiene reglas estáticas configuradas.') % report_type,
                    'explanation': _('Este reporte no tiene definido un perfil de auditoría estática.'),
                    'solution': _('Contacte a soporte técnico para agregar validaciones contables a este reporte.')
                }]
        except Exception as e:
            _logger.exception("Error during static financial report audit")
            return _("<h3>Error al realizar la auditoría</h3><p>%s</p>") % str(e)

        return self._generate_html_report(anomalies, report_type)

    def _run_ai_audit(self, wizard, report_type):
        summary = ""
        try:
            if report_type == 'trial_balance':
                summary = self._get_trial_balance_summary(wizard)
            elif report_type == 'general_ledger':
                summary = self._get_general_ledger_summary(wizard)
            elif report_type in ('partner_ledger', 'partner_ageing'):
                summary = self._get_partner_summary(wizard, report_type)
            elif report_type in ('balance_sheet', 'profit_loss'):
                summary = self._get_financial_reports_summary(wizard, report_type)
            else:
                summary = _("Datos del reporte no serializables.")
        except Exception as e:
            _logger.exception("Error serializing report for AI")
            return _("<p>Error al preparar los datos para la IA: %s</p>") % str(e)

        return self._call_lm_studio(report_type, summary)

    # --- Data Serialization Helpers for AI ---

    def _get_trial_balance_summary(self, wizard):
        data = wizard.view_report([wizard.id])
        report_lines = data.get('report_lines', [])
        summary = f"Total Débitos: {data.get('debit_total', 0.0)}\nTotal Créditos: {data.get('credit_total', 0.0)}\n\nDetalle de Cuentas:\n"
        for line in report_lines:
            summary += f"- Cuenta {line.get('code')} - {line.get('name')}: Débito={line.get('debit')}, Crédito={line.get('credit')}, Saldo Neto={line.get('balance')}\n"
        return summary

    def _get_general_ledger_summary(self, wizard):
        title = wizard.titles or 'General Ledger'
        data = wizard.view_report([wizard.id], title)
        report_lines = data.get('report_lines', [])
        summary = f"Libro Mayor: {title}\nTotal Débitos: {data.get('debit_total', 0.0)}\nTotal Créditos: {data.get('credit_total', 0.0)}\n\nSaldos de Cuentas:\n"
        for line in report_lines:
            summary += f"- Cuenta {line.get('code')} - {line.get('name')}: Débito={line.get('debit')}, Crédito={line.get('credit')}, Saldo Neto={line.get('balance')}\n"
        return summary

    def _get_partner_summary(self, wizard, report_type):
        data = wizard.view_report([wizard.id])
        report_lines = data.get('report_lines', [])
        summary = f"Libro de Terceros (Tipo: {report_type}):\n\nSaldos por Tercero:\n"
        for line in report_lines:
            if report_type == 'partner_ageing':
                summary += f"- Tercero {line.get('name')}: Total={line.get('total')}, 0-30={line.get('direction_four')}, 30-60={line.get('direction_three')}, 60-90={line.get('direction_two')}, 90+={line.get('direction_one')}\n"
            else:
                summary += f"- Tercero {line.get('name')}: Débito={line.get('debit')}, Crédito={line.get('credit')}, Saldo Neto={line.get('balance')}\n"
        return summary

    def _get_financial_reports_summary(self, wizard, report_type):
        tag = 'de_balance' if report_type == 'balance_sheet' else 'de_profit_loss'
        data = wizard.view_report([wizard.id], tag)
        report_lines = data.get('report_lines', [])
        summary = f"Reporte Financiero ({report_type}):\n\nSaldos de Cuentas:\n"
        for line in report_lines:
            summary += f"- {line.get('name')}: Saldo={line.get('balance')}\n"
        return summary

    # --- LM-Studio API Call ---

    def _call_lm_studio(self, report_type, data_summary):
        url = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_url')
        key = self.env['ir.config_parameter'].sudo().get_param('lm_studio.api_key')
        model = self.env['ir.config_parameter'].sudo().get_param('lm_studio.model') or 'lmstudio-community/meta-llama-3-8b-instruct'

        if not url or not key:
            return _("<p>Error: LM-Studio API no está configurada.</p>")

        # Clean/Normalize URL to ensure chat completions endpoint
        if not url.endswith('/chat/completions'):
            url = url.rstrip('/')
            if not url.endswith('/v1'):
                url += '/v1'
            url += '/chat/completions'

        prompt = f"""
        Actúa como un Auditor Contable y Financiero profesional. Analiza el siguiente reporte financiero de Odoo (Tipo: {report_type}):
        
        {data_summary}
        
        Identifica cualquier descuadre contable, saldos invertidos e inusuales, o discrepancias.
        Presenta el resultado formateado en código HTML limpio y moderno para mostrar en la interfaz de Odoo (usa Bootstrap si lo deseas).
        Tu reporte debe contener las siguientes secciones:
        1. Resumen Ejecutivo del Análisis Inteligente
        2. Hallazgos y Anomalías Clave Detectadas
        3. Explicación Contable del Por Qué ocurre
        4. Acciones Sugeridas para Solucionarlo
        
        IMPORTANTE: Responde únicamente con código HTML limpio. No agregues bloques de código markdown como ```html al principio o final.
        """

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Eres un auditor financiero experto. Respondes únicamente con código HTML válido, estructurado y sin marcas markdown."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', f'Bearer {key}')

            with urllib.request.urlopen(req, timeout=45) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                choices = res_data.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content', '')
                    if content.startswith('```html'):
                        content = content.replace('```html', '', 1).replace('```', '', 1)
                    elif content.startswith('```'):
                        content = content.replace('```', '', 1).replace('```', '', 1)
                    return content.strip()
                return _("<p>Error: No se recibió respuesta del modelo desde LM-Studio.</p>")
        except urllib.error.HTTPError as e:
            _logger.exception("LM-Studio HTTP Error")
            try:
                error_body = e.read().decode('utf-8')
                error_json = json.loads(error_body)
                error_message = error_json.get('error', {}).get('message', error_body)
            except Exception:
                error_message = str(e)
            return _("<p>Error HTTP de LM-Studio (Código %s): %s. Detalle: %s</p>") % (e.code, e.reason, error_message)
        except URLError as e:
            _logger.exception("Failed to connect to LM-Studio")
            return _("<p>Error al conectar con LM-Studio en %s: %s. Verifique que LM-Studio esté ejecutándose localmente o en el servidor especificado.</p>") % (url, str(e.reason))
        except Exception as e:
            _logger.exception("Failed to analyze report with LM-Studio")
            return _("<p>Error inesperado durante el análisis con IA: %s</p>") % str(e)

    # --- Static Audit Engine Helpers ---

    def _audit_trial_balance(self, wizard):
        data = wizard.view_report([wizard.id])
        report_lines = data.get('report_lines', [])
        debit_total = data.get('debit_total', 0.0)
        credit_total = data.get('credit_total', 0.0)
        anomalies = []

        if abs(debit_total - credit_total) > 0.01:
            anomalies.append({
                'type': 'critical',
                'title': _('Desbalance en Balance de Comprobación'),
                'desc': _('El total de Débitos (%.2f) no es igual al total de Créditos (%.2f).') % (debit_total, credit_total),
                'explanation': _('El principio fundamental de partida doble se encuentra vulnerado. Cada transacción debe tener valores iguales de débito y crédito.'),
                'solution': _('Ejecute un análisis de los asientos contables en estado "Publicado" para encontrar discrepancias de redondeo o importación.')
            })

        for line in report_lines:
            account = self.env['account.account'].search([('code', '=', line.get('code'))], limit=1)
            if not account:
                continue
            internal_group = account.user_type_id.internal_group
            balance = line.get('balance', 0.0)
            debit = line.get('debit', 0.0)
            credit = line.get('credit', 0.0)

            if internal_group in ('asset', 'expense') and balance < -0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Saldo Acreedor Inusual en Activo/Gasto: %s (%s)') % (account.name, account.code),
                    'desc': _('La cuenta tiene un saldo acreedor de %.2f (Débito: %.2f, Crédito: %.2f).') % (abs(balance), debit, credit),
                    'explanation': _('Las cuentas de activo y gasto normalmente tienen saldos deudores. Un saldo acreedor en Caja/Bancos indica un sobregiro real o pagos registrados antes de sus respectivos ingresos.'),
                    'solution': _('Realice una conciliación de caja/banco. Revise que los depósitos e ingresos del periodo se hayan registrado por completo.')
                })
            elif internal_group in ('liability', 'equity', 'income') and balance > 0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Saldo Deudor Inusual en Pasivo/Patrimonio/Ingreso: %s (%s)') % (account.name, account.code),
                    'desc': _('La cuenta tiene un saldo deudor de %.2f (Débito: %.2f, Crédito: %.2f).') % (balance, debit, credit),
                    'explanation': _('Las cuentas de pasivo, patrimonio e ingresos normalmente tienen saldos acreedores. Un saldo deudor aquí puede indicar cobros excesivos/anticipos a proveedores sin aplicar, o anulaciones erróneas.'),
                    'solution': _('Examine las facturas de proveedor o asientos de ajuste asociados a esta cuenta.')
                })
        return anomalies

    def _audit_general_ledger(self, wizard):
        title = wizard.titles or 'General Ledger'
        data = wizard.view_report([wizard.id], title)
        report_lines = data.get('report_lines', [])
        anomalies = []

        for account_data in report_lines:
            account = self.env['account.account'].search([('code', '=', account_data.get('code'))], limit=1)
            if not account:
                continue
            internal_group = account.user_type_id.internal_group
            balance = account_data.get('balance', 0.0)

            if internal_group in ('asset', 'expense') and balance < -0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Saldo Neto Negativo en %s') % account_data.get('name'),
                    'desc': _('Cuenta de Activo/Gasto finalizó con saldo acreedor de %.2f.') % abs(balance),
                    'explanation': _('El saldo neto acumulado al cierre del periodo es negativo, lo cual es inusual para este tipo de cuentas.'),
                    'solution': _('Audite los asientos individuales en el Libro Mayor de esta cuenta para detectar duplicados o transacciones invertidas.')
                })
            elif internal_group in ('liability', 'equity', 'income') and balance > 0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Saldo Neto Invertido en %s') % account_data.get('name'),
                    'desc': _('Cuenta de Pasivo/Patrimonio/Ingreso finalizó con saldo deudor de %.2f.') % balance,
                    'explanation': _('El saldo neto acumulado al cierre es deudor, lo que indica un posible error de registro.'),
                    'solution': _('Verifique si se registraron devoluciones de ventas o anticipos de manera directa sin cruzarlos con el documento origen.')
                })
        return anomalies

    def _audit_partner_ledger(self, wizard):
        data = wizard.view_report([wizard.id])
        report_lines = data.get('report_lines', [])
        anomalies = []

        for partner_line in report_lines:
            balance = partner_line.get('balance', 0.0)
            partner_name = partner_line.get('name', 'Desconocido')
            
            if balance < -0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Saldo Negativo del Tercero: %s') % partner_name,
                    'desc': _('El tercero tiene un saldo a favor (negativo) de %.2f.') % abs(balance),
                    'explanation': _('Un saldo total negativo en cuentas de terceros (como clientes) representa un saldo a favor de ellos, posiblemente debido a un pago recibido en exceso o anticipos sin facturar.'),
                    'solution': _('Revise los pagos pendientes de conciliar con facturas para este tercero. Si es un cliente, asocie su anticipo a la factura correspondiente.')
                })
        return anomalies

    def _audit_partner_ageing(self, wizard):
        data = wizard.view_report([wizard.id])
        report_lines = data.get('report_lines', [])
        anomalies = []

        for partner_line in report_lines:
            total = partner_line.get('total', 0.0)
            partner_name = partner_line.get('name', 'Desconocido')

            if total < -0.01:
                anomalies.append({
                    'type': 'warning',
                    'title': _('Saldo de Antigüedad Negativo en %s') % partner_name,
                    'desc': _('El saldo vencido acumulado es negativo: %.2f.') % abs(total),
                    'explanation': _('Un saldo de antigüedad negativo indica notas de crédito aplicadas sin factura destino o pagos realizados sin deuda registrada en la fecha de corte.'),
                    'solution': _('Valide la fecha de corte del reporte de antigüedad y cruce las notas de crédito abiertas con las facturas vencidas.')
                })
        return anomalies

    def _audit_financial_reports(self, wizard, report_type):
        tag = 'de_balance' if report_type == 'balance_sheet' else 'de_profit_loss'
        data = wizard.view_report([wizard.id], tag)
        report_lines = data.get('report_lines', [])
        anomalies = []

        if report_type == 'balance_sheet':
            assets_total = 0.0
            liabilities_total = 0.0
            equity_total = 0.0

            for line in report_lines:
                name = line.get('name', '').lower()
                balance = line.get('balance', 0.0)
                if 'activo' in name or 'asset' in name:
                    assets_total = balance
                elif 'pasivo' in name or 'liability' in name:
                    liabilities_total = balance
                elif 'patrimonio' in name or 'equity' in name or 'capital' in name:
                    equity_total = balance

            calculated_diff = abs(assets_total - (liabilities_total + equity_total))
            if calculated_diff > 1.0:
                anomalies.append({
                    'type': 'critical',
                    'title': _('Ecuación Patrimonial Descuadrada'),
                    'desc': _('El total de Activos (%.2f) no coincide con la suma de Pasivos (%.2f) y Patrimonio (%.2f). Diferencia: %.2f') % (assets_total, liabilities_total, equity_total, calculated_diff),
                    'explanation': _('El balance general no está balanceado. Esto suele suceder por configuraciones erróneas en los tipos de cuenta contable, cuentas huérfanas sin jerarquía o asientos de diario manuales directamente en el patrimonio.'),
                    'solution': _('Revise la configuración de la estructura del reporte financiero. Asegúrese de que todas las cuentas nuevas creadas estén asignadas a un tipo de cuenta con su respectiva categoría.')
                })
        return anomalies

    def _generate_html_report(self, anomalies, report_type):
        html = """
        <div style="font-family: Arial, sans-serif; padding: 15px;">
            <div style="background-color: #f8f9fa; border-left: 5px solid #00A0AD; padding: 10px; margin-bottom: 20px; border-radius: 4px;">
                <h4 style="margin: 0; color: #00A0AD;">🛡️ Panel de Auditoría Contable (Reglas Estáticas)</h4>
                <p style="margin: 5px 0 0 0; font-size: 13px; color: #6c757d;">
                    Este análisis fue realizado de forma estática en base a las reglas de consistencia de partida doble, naturaleza de saldos e integridad de cuentas.
                </p>
            </div>
        """

        if not anomalies:
            html += """
            <div style="background-color: #d4edda; border-color: #c3e6cb; color: #155724; padding: 15px; border-radius: 4px; text-align: center;">
                <h4 style="margin-top: 0;">✅ ¡Enhorabuena! No se encontraron anomalías críticas</h4>
                <p style="margin-bottom: 0; font-size: 14px;">
                    Las cifras del reporte coinciden y cumplen con las reglas básicas de coherencia y partida doble contable.
                </p>
            </div>
            """
        else:
            html += "<h5>Anomalías y Advertencias Detectadas:</h5>"
            for idx, anomaly in enumerate(anomalies):
                color = "#dc3545" if anomaly.get('type') == 'critical' else "#ffc107"
                bg_color = "#f8d7da" if anomaly.get('type') == 'critical' else "#fff3cd"
                border_color = "#f5c6cb" if anomaly.get('type') == 'critical' else "#ffeeba"
                badge_text = "Crítico" if anomaly.get('type') == 'critical' else "Advertencia"

                html += f"""
                <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-left: 5px solid {color}; padding: 15px; border-radius: 4px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <strong style="font-size: 15px; color: #333;">{anomaly.get('title')}</strong>
                        <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">
                            {badge_text}
                        </span>
                    </div>
                    <p style="margin: 5px 0; font-size: 13.5px; font-weight: bold; color: #333;">Detalle: {anomaly.get('desc')}</p>
                    <p style="margin: 5px 0; font-size: 13px; color: #555;"><strong>Explicación:</strong> {anomaly.get('explanation')}</p>
                    <p style="margin: 5px 0; font-size: 13px; color: #222; background-color: #ffffff; padding: 8px; border-radius: 4px; border: 1px dashed #ccc;">
                        <strong>🛠️ Acción de Corrección:</strong> {anomaly.get('solution')}
                    </p>
                </div>
                """
        html += "</div>"
        return html
