import requests
import base64
import html2text
from odoo import models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WhatsappModeMessage:
    _name = 'whatsapp.mode.message'

    def __init__(self,env):
        self.env = env
        self.evolution_base_url = self.env['ir.config_parameter'].sudo().get_param(
            'all_in_one_whatsapp_integration.evolution_base_url')
        self.evolution_instance = self.env['ir.config_parameter'].sudo().get_param(
            'all_in_one_whatsapp_integration.evolution_instance')
        self.evolution_apikey = self.env['ir.config_parameter'].sudo().get_param(
            'all_in_one_whatsapp_integration.evolution_apikey')

    def clean_number(self, number):
        if not isinstance(number,str):
            number = str(number)
        return number.replace(" ","").replace("+","")
    
    def build_URL(self, type_msg ):
        return f"{self.evolution_base_url}/message/{type_msg}/{self.evolution_instance}"
    
    def send_request_whatsapp(self,url,payload):
        response = None
        headers = {            
                'Content-Type': 'application/json',
                'apikey': self.evolution_apikey
            }
        try:
            response = requests.post(url,json=payload,headers=headers)
            if response.status_code == 200:                
                _logger.info("Mensaje WhatsApp enviado correctamente")
            else:
                _logger.error(f"Error al enviar mensaje: {response.status_code} {response.text}")
        except Exception as e:
            _logger.exception(f"Error al conectar con Evolution API: {e}")

        return response

    def action_send_custom_message(self, number, whatsapp_message):
        number = self.clean_number(number)        
        type_msg = "sendText"
        url = self.build_URL(type_msg)    
        #url = f"{self.evolution_base_url}/message/sendText/{self.evolution_instance}"
        payload = {
                "number": number,
                "options":{
                    "delay":1200,
                    "presence": "composing",
                    "linkPreview": False
                },
                "textMessage":{
                    "text": whatsapp_message
                }
            }        
        return self.send_request_whatsapp(url,payload)
    
    def action_send_image_url_message(self, number, whatsapp_message):
        pass

    def action_send_video_media_url_message(self, number, whatsapp_message, media_message):
        number = self.clean_number(number)
        type_msg= "sendMedia"
        url = self.build_URL(type_msg)

        payload = {
                "number": number,
                "options":{
                    "delay":1200,
                    "presence": "composing",
                },
                "mediaMessage":{
                    "mediatype": "video",
                    "caption": whatsapp_message,
                    "media": media_message
                }
            }      
        return self.send_request_whatsapp(url,payload)
    
    def action_send_PDF_document_url_message(self, number, file_name, whatsapp_message, mediaPDF_message):
        number = self.clean_number(number)
        type_msg= "sendMedia"
        url = self.build_URL(type_msg)

        payload = {
                "number": number,
                "options":{
                    "delay":1200,
                    "presence": "composing",
                },
                "mediaMessage":{
                    "mediatype": "document",
                    "fileName": f"{file_name}.pdf",
                    "caption": whatsapp_message,
                    "media": mediaPDF_message
                }
            }                    
        return self.send_request_whatsapp(url,payload)