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
import requests
import logging
import urllib.parse as parse
from twilio.rest import Client
from odoo import fields, models
from .whatsapp_mode_message import WhatsappModeMessage

_logger = logging.getLogger(__name__)

class SendWhatsappMessage(models.TransientModel):
    """ This function helps to send a message to a user."""
    _name = 'send.whatsapp.message'
    _description = "Helps to send messages using different way"

    def _get_mode_selection(self):
        options = [('web', 'WhatsApp Web')]
        twilio_whatsapp_enabled = (self.env["ir.config_parameter"].sudo().get_param
                    ("all_in_one_whatsapp_integration.twilio_enabled"))
        cloud_api_enabled = (self.env["ir.config_parameter"].sudo().get_param
                    ("all_in_one_whatsapp_integration.cloud_api_enabled"))
        evolution_api_enabled = (self.env["ir.config_parameter"].sudo().get_param
                    ("all_in_one_whatsapp_integration.evolution_api_enabled"))
        if(twilio_whatsapp_enabled):
            options.append(('twilio', 'Twilio'))
        if(cloud_api_enabled):
            options.append(('cloud', 'Cloud WhatsApp'))
        if(evolution_api_enabled):
            options.append(('evolution', 'Evolution WhatsApp'))


        return options


    sale_user_id = fields.Many2one('res.partner',
                                   string="Partner Name",
                                   default=lambda self: self.env[
                                       self._context.get('active_model')]
                                   .browse(self.env.context.get('active_ids'))
                                   .partner_id,
                                   help="Select the partner associated with "
                                        "the sale.")
    whatsapp_mobile_number = fields.Char(related='sale_user_id.mobile',
                                         required=True,
                                         help="The mobile number associated"
                                              " with the selected partner.")
    whatsapp_message = fields.Text(string="WhatsApp Message",
                                   help="Enter the message to be sent via "
                                        "WhatsApp.")
    send_mode = fields.Selection(_get_mode_selection,
                                 string="Send Using", default='web',
                                 help="Select the mode to send the WhatsApp"
                                      " message.")
    attachment_ids = fields.Many2many('ir.attachment',
                                      'whatsapp_attachment_rel',
                                      'email_template_id',
                                      'attachment_id',
                                      string='Attachments',
                                      help="Attachments to include in the"
                                           " WhatsApp message.")
    message_type = fields.Selection(string='Message Type',
                                    selection=[('text', 'Text'),
                                               ('document', 'Document')],
                                    default='text')

    def action_send_custom_message(self):
        """This function helps to send a message to a user."""
        base_url = self.get_base_url()
        attachment = self.env['ir.attachment'].browse(
            self.attachment_ids.ids[0])
        attachment.public = True
        file_link = base_url + ('/web/content/?model=ir.attachment&id='
                + str(self.attachment_ids.ids[0]) + '&download=true')
        number = self.sale_user_id.mobile
        if self.send_mode == 'twilio':
            if " " in number:
                number = number.replace(" ", "")
            account_sid = self.env['ir.config_parameter'].sudo().get_param(
                'all_in_one_whatsapp_integration.account_sid')
            auth_token = self.env['ir.config_parameter'].sudo().get_param(
                'all_in_one_whatsapp_integration.auth_token')
            twilio_whatsapp = self.env['ir.config_parameter'].sudo().get_param(
                'all_in_one_whatsapp_integration.twilio_whatsapp')
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                from_='whatsapp:' + twilio_whatsapp,
                body=self.whatsapp_message,
                to='whatsapp:' + str(number),
            )
            return message
        elif self.send_mode == 'web':
            message_string = parse.quote(self.whatsapp_message)
            message_string = message_string[:(len(message_string) - 3)]
            number = self.sale_user_id.mobile
            link = "https://web.whatsapp.com/send?phone=" + number
            send_msg = {
                'type': 'ir.actions.act_url',
                'url': link + "&text=" + message_string,
                'target': 'new',
                'res_id': self.id,
            }
            return send_msg
        elif self.send_mode == 'cloud':
            var = 'body'
            bearer_token = self.env['ir.config_parameter'].sudo().get_param(
                'all_in_one_whatsapp_integration.bearer_token')
            whatsapp_no = self.env['ir.config_parameter'].sudo().get_param(
                'all_in_one_whatsapp_integration.whatsapp_no')
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": number,
                "type": self.message_type,
                "preview_url": False,
            }
            if self.message_type == 'text':
                payload["text"] = {
                    "preview_url": False,
                    var: self.whatsapp_message
                }
            elif self.message_type == 'document':
                
                # payload["text"] = {
                #     "preview_url": False,
                #     var: "url pdf: "+file_link
                # }
                payload["document"] = {
                    "link": file_link,
                    "caption": "documento pdf"
                }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {bearer_token}'
            }
            response = requests.post(
                f"https://graph.facebook.com/v17.0/{whatsapp_no}/messages",
                json=payload,
                headers=headers
            )
            return response
        elif self.send_mode == 'evolution':
            whatsapp_message_mode = WhatsappModeMessage(self.env)
            return whatsapp_message_mode.action_send_custom_message(number,self.whatsapp_message)
            #return whatsapp_message_mode.action_send_PDF_document_url_message(number,"invoicereport",self.whatsapp_message,  "https://evolution-api.com/files/evolution-api.pdf")
            # if " " in number:            
            #     number = number.replace(" ", "").replace("+","")
            # evolution_base_url = self.env['ir.config_parameter'].sudo().get_param(
            #     'all_in_one_whatsapp_integration.evolution_base_url')
            # evolution_instance = self.env['ir.config_parameter'].sudo().get_param(
            #     'all_in_one_whatsapp_integration.evolution_instance')
            # evolution_apikey = self.env['ir.config_parameter'].sudo().get_param(
            #     'all_in_one_whatsapp_integration.evolution_apikey')
            # url = f"{evolution_base_url}/message/sendText/{evolution_instance}"

            # payload = {
            #     "number": number,
            #     "options":{
            #         "delay":1200,
            #         "presence": "composing",
            #         "linkPreview": False
            #     },
            #     "textMessage":{
            #         "text": self.whatsapp_message
            #     }              
            # }
            # headers = {
            #     'Content-Type': 'application/json',
            #     'apikey': evolution_apikey
            # }
            # response = None 
            # try:
            #     response = requests.post(url, json=payload, headers=headers)
            #     if response.status_code == 200:
            #         _logger.info(f"Mensaje WhatsApp enviado correctamente a {self.sale_user_id.name}: {response.text}")
            #     else:
            #         _logger.error(f"Error al enviar mensaje a {self.sale_user_id.name}: {response.status_code} {response.text}")
            # except Exception as e:
            #     _logger.exception(f"Error al conectar con Evolution API: {e}")

            # return response