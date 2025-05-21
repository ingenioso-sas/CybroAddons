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
    
    def build_payload_whatsapp(self, number, extra_options=None, extra_sections=None):
        
        base_options = {
            "delay": 1200,
            "presence": "composing"
        }

        if extra_options:            
            base_options.update(extra_options)                

        payload = {
            "number": number,
            "options": extra_options,
        }

        if extra_sections:
            payload.update(extra_sections)

        return payload
    
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
        # base_options = {
        #     "linkPreview": False
        # }
        # extra_sections = {
        #     "textMessage":{
        #             "text": whatsapp_message
        #         }
        # }
        # payload = self.build_payload_whatsapp(number, base_options, extra_sections)
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
    
    def action_send_image_message(self, number, whatsapp_message, message_type_media):
        """
        Envía un mensaje de WhatsApp con una imagen adjunta utilizando la API EVOLUTION.

        Parámetros:
        -----------
        number : str  
            Número de teléfono del destinatario en formato internacional, sin espacios ni signos.  
            Ejemplo: "573113492020".

        whatsapp_message : str  
            Mensaje de texto que se enviará junto con la imagen. Puede incluir formato enriquecido como negritas, saltos de línea, etc.

        message_type_media : str  
            Representación de la imagen a enviar. Se admiten dos tipos de entrada:
                - Cadena codificada en **Base64** que contiene los datos binarios de la imagen.  
                - **URL pública** desde donde se puede descargar la imagen.        

        Requisitos:
        -----------            
        - Los formatos compatibles suelen incluir `.jpg`, `.jpeg`, `.png`, entre otros aceptados por WhatsApp.

        Aplicaciones comunes:
        ---------------------
        - Envío de comprobantes visuales.
        - Promociones o anuncios visuales.
        - Información gráfica relacionada con órdenes, productos o servicios.
        """
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
                    "mediatype": "image",
                    "caption": whatsapp_message,
                    "media": message_type_media
                }
            }      
        return self.send_request_whatsapp(url,payload)
        

    def action_send_video_message(self, number, whatsapp_message, message_type_media):
        """
        Envía un mensaje de WhatsApp con un archivo de video adjunto, utilizando la API EVOLUTION.

        Parámetros:
        -----------
        number : str  
            Número de teléfono del destinatario en formato internacional, sin espacios ni signos.  
            Ejemplo: "573113492020".

        whatsapp_message : str  
            Texto del mensaje que se enviará junto con el video. Puede incluir formato como negritas, saltos de línea, etc.

        message_type_media : str  
            Contenido del video a enviar. Se admiten dos tipos de entrada:
                - Una cadena codificada en **Base64** que representa el archivo de video.  
                - Una **URL pública** desde donde se puede descargar el archivo.
        Requisitos:
        -----------
        - El archivo de video debe estar codificado correctamente en base64 o disponible en una URL válida y pública.
        - El formato del archivo debe ser compatible con WhatsApp (por ejemplo: `.mp3`).
        """
        number = self.clean_number(number)
        type_msg= "sendMedia"
        url = self.build_URL(type_msg)

        payload = {
                "number": number,
                "options":{
                    "delay":1200,
                    "presence": "composing"
                },
                "mediaMessage":{
                    "mediatype": "video",
                    "caption": whatsapp_message,
                    "media": message_type_media
                }
            }      
        return self.send_request_whatsapp(url,payload)
    
    def action_send_attachment_document_message(self, number, file_name, whatsapp_message, message_type_media):
        """
        Envía un mensaje de WhatsApp con un documento adjunto, ya sea codificado en base64 o a través de una URL, utilizando la API EVOLUTION.
        
        Parámetros:
        -----------
        number : str
            Número de teléfono del destinatario en formato internacional, sin espacios ni signos.
            Ejemplo: "573113492020".

        file_name : str
            Nombre del archivo que se enviará como adjunto. Puede incluir extensiones como `.pdf`, `.xlsx`, `.zip`
            Ejemplos:\n
                - "invoice_2025_05_20.pdf".
                - "evolution-api.xlsx".
                - "evolution-api.zip"

        whatsapp_message : str
            Mensaje de texto que se enviará junto con el documento. Puede incluir texto con formato como negrillas o saltos de línea.

        message_type_media : str
            Contenido del archivo adjunto. Admite dos tipos de entrada:
                    \n- Archivo  codificado en formato base64 que será enviado como adjunto en el mensaje. Este valor debe ser una cadena base64 válida.
                    \n- Una **URL válida** que apunte al archivo alojado de forma pública.
        """
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
                    "fileName": file_name,
                    "caption": whatsapp_message,
                    "media": str(message_type_media)
                }
            }                    
        return self.send_request_whatsapp(url,payload)

    def action_send_sticker_message(self, number, message_type_media):
        """
        Envía un mensaje de WhatsApp con un sticker utilizando la API de EVOLUTION.

        Parámetros:
        -----------
        number : str
            Número de teléfono del destinatario en formato internacional, sin espacios ni símbolos,
            por ejemplo: "573103947320".

        message_type_media : str
            Puede ser una de dos formas válidas:
            - Una cadena codificada en base64 que representa el archivo del sticker (formato .png).
            - Una URL válida que apunte a un archivo .webp accesible públicamente.
        """
        number = self.clean_number(number)
        type_msg= "sendSticker"
        url = self.build_URL(type_msg)

        payload = {
                "number": number,
                "options":{
                    "delay": 1200,
                    "presence": "composing"
                },
                "stickerMessage": {
                    "image": str(message_type_media)
                }
        }
        return self.send_request_whatsapp(url,payload)

    def action_send_audio_message(self, number, message_type_media):
        """
        Envía un mensaje de audio a través de WhatsApp utilizando la API de EVOLUTION.

        Parámetros:
        -----------
        number : str
            Número de teléfono del destinatario en formato internacional, sin espacios ni símbolos,
            por ejemplo: "573103947320".

        message_type_media : str
            Contenido del archivo de audio que será enviado. Puede ser:
            - Una cadena codificada en base64 que representa el archivo de audio (formato .mp3).
            - Una URL válida que apunte a un archivo de audio accesible públicamente.
       
        Ejemplo de uso:
        ---------------
        self.action_send_audio_message("573103947320", "https://example.com/audio.mp3")
        """
        number = self.clean_number(number)
        type_msg= "sendWhatsAppAudio"
        url = self.build_URL(type_msg)

        payload = {
                "number": number,
                "options":{
                    "delay": 1200,
                    "presence": "recording",
                    "encoding": True
                },
                "audioMessage": {
                    "audio": str(message_type_media)
                }
        }
        return self.send_request_whatsapp(url,payload)
