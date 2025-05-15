# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (Contact : odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """ Inherited this module is to add fields for WhatsApp's
        message-sending authentication """
    _inherit = "res.config.settings"

    account_sid = fields.Char(string="Account SID",
                              config_parameter='all_in_one_whatsapp_integration.'
                                               'account_sid',
                              help="Account SID of twilio account", )
    auth_token = fields.Char(string="Auth Token",
                             config_parameter='all_in_one_whatsapp_integration.'
                                              'auth_token',
                             help="Auth Token of twilio account")
    twilio_whatsapp = fields.Char(string="Twilio Whatsapp Number",
                                  config_parameter='all_in_one_whatsapp_integration'
                                                   '.twilio_whatsapp',
                                  help="Whatsapp number of twilio account")
    twilio_whatsapp_enabled = fields.Boolean(string="Twilio whatsapp Enabled",
                                config_parameter='all_in_one_whatsapp_integration'
                                                   '.twilio_enabled',
                                help="Enabled Whatsapp twilio account")
                                
    bearer_token = fields.Char(string="Whatsapp Access Token",
                               help="Authorization Token of Whatsapp Cloud "
                                    "API",
                               config_parameter='all_in_one_whatsapp_integration.'
                                                'bearer_token', )
    whatsapp_no = fields.Char(string="Phone number ID",
                              help="Phone Number ID of Whatsapp Cloud API",
                              config_parameter='all_in_one_whatsapp_integration.'
                                               'whatsapp_no', )
    whatsapp_business = fields.Char(help="Business ID of Whatsapp Cloud API",
                                    string="Whatsapp Business Account ID",
                                    config_parameter='whatsapp_integration_'
                                                     'odoo.whatsapp_business', )
    cloud_api_enabled = fields.Boolean(string="Cloud API whatsapp Enabled",
                                config_parameter='all_in_one_whatsapp_integration'
                                                   '.cloud_api_enabled',
                                help="Enabled Whatsapp twilio account")
    
    evolution_api_enabled = fields.Boolean(string="Evolution API whatsapp Enabled",
                                config_parameter='all_in_one_whatsapp_integration'
                                                   '.evolution_api_enabled',
                                help="Enabled API Evoution For Whatsapp")
    
    evolution_base_url = fields.Char(string="Url base",
                              help="Url base for Evolution API",
                              config_parameter='all_in_one_whatsapp_integration.'
                                               'evolution_base_url',)
    
    evolution_instance = fields.Char(string="Instance",
                              help="Instance for Evolution API",
                              config_parameter='all_in_one_whatsapp_integration.'
                                               'evolution_instance',)

    evolution_apikey = fields.Char(string="apiKey",
                              help="URL apikey for Evolution API",
                              config_parameter='all_in_one_whatsapp_integration.'
                                               'evolution_apikey',)                                