# -*- coding: utf-8 -*-
"""Excepciones compartidas del módulo WhatsApp."""
from odoo.exceptions import UserError


class WhatsappPermanentError(UserError):
    """Error no recuperable que no debe reintentarse automáticamente.

    Se usa para respuestas 4xx del proveedor (excepto 408/429) y para
    configuraciones/parámetros inválidos que no se corrigen solos.
    """
