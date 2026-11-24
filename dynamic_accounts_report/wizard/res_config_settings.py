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
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_static_audit = fields.Boolean(string='Enable Static Audit')
    enable_ai_audit = fields.Boolean(string='Enable AI Audit')
    lm_studio_api_url = fields.Char(
        string='AI Server URL', config_parameter='lm_studio.api_url')
    lm_studio_api_key = fields.Char(
        string='AI API Key', config_parameter='lm_studio.api_key')
    lm_studio_model = fields.Char(
        string='AI Model', config_parameter='lm_studio.model',
        default='lmstudio-community/meta-llama-3-8b-instruct')

    def get_values(self):
        result = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        result.update({
            'enable_static_audit': params.get_param(
                'lm_studio.enable_static_audit', 'True') == 'True',
            'enable_ai_audit': params.get_param(
                'lm_studio.enable_ai_audit', 'False') == 'True',
        })
        return result

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(
            'lm_studio.enable_static_audit', str(self.enable_static_audit))
        params.set_param(
            'lm_studio.enable_ai_audit', str(self.enable_ai_audit))
