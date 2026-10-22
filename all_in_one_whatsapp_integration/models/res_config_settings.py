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
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Ajustes propios de WhatsApp: proveedores, credenciales, cola y pruebas."""
    _inherit = "res.config.settings"

    @api.model
    def _default_providers(self):
        return self.env["whatsapp.provider"].search([])

    provider_ids = fields.Many2many(
        "whatsapp.provider", string="Proveedores",
        default=_default_providers,
        help="Canales de envío. Solo los habilitados aparecen en el "
             "wizard y son procesados por la cola.")
    whatsapp_async_default = fields.Boolean(
        string="Encolar por defecto",
        config_parameter="all_in_one_whatsapp_integration.whatsapp_async_default",
        help="Si está activo, el wizard propone encolar el mensaje en "
             "lugar de enviarlo al momento.")
    whatsapp_queue_limit = fields.Integer(
        string="Mensajes por ciclo",
        config_parameter="all_in_one_whatsapp_integration.whatsapp_queue_limit",
        default=20,
        help="Cuántos mensajes pendientes procesa el cron en cada ciclo.")
    whatsapp_queue_max_retries = fields.Integer(
        string="Reintentos máximos",
        config_parameter="all_in_one_whatsapp_integration.whatsapp_queue_max_retries",
        default=5,
        help="Tras este número de fallos el mensaje queda en Error y "
             "ya no se reintenta solo.")
    whatsapp_test_phone = fields.Char(
        string="Teléfono de prueba",
        config_parameter="all_in_one_whatsapp_integration.whatsapp_test_phone",
        help="Número E.164 (ej. +573001234567) usado por los botones "
             "de prueba de conexión.")

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
                                    config_parameter='all_in_one_whatsapp_integration.'
                                                     'whatsapp_business', )
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
    webhook_verify_token = fields.Char(
        string="Webhook Verify Token",
        config_parameter='all_in_one_whatsapp_integration.'
                         'webhook_verify_token',
        help="Token configured in Meta App to verify GET /whatsapp_message")                                