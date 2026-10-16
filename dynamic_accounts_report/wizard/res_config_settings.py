# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_static_audit = fields.Boolean(string='Permitir Análisis Estático')
    enable_ai_audit = fields.Boolean(string='Permitir Análisis con IA')
    
    lm_studio_api_url = fields.Char(string='URL del Servidor de IA', config_parameter='lm_studio.api_url')
    lm_studio_api_key = fields.Char(string='Token de la IA', config_parameter='lm_studio.api_key')
    lm_studio_model = fields.Char(string='Modelo de la IA', config_parameter='lm_studio.model', default='lmstudio-community/meta-llama-3-8b-instruct')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            enable_static_audit=params.get_param('lm_studio.enable_static_audit', 'True') == 'True',
            enable_ai_audit=params.get_param('lm_studio.enable_ai_audit', 'True') == 'True',
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('lm_studio.enable_static_audit', str(self.enable_static_audit))
        params.set_param('lm_studio.enable_ai_audit', str(self.enable_ai_audit))
