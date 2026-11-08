# -*- coding: utf-8 -*-
"""Punto único de lógica WhatsApp para documentos (sale/purchase/invoice/picking).

Evita la cuadruplicación de validaciones, render de plantillas y PDFs
que existía en sale_order.py / purchase_order.py / account_move.py /
stock_picking.py con sutiles divergencias y crashes con valores None.
"""
import base64
import logging

import html2text

from odoo import _, api, models
from odoo.exceptions import ValidationError

from . import whatsapp_tools as tools

_logger = logging.getLogger(__name__)


class WhatsappDocumentService(models.AbstractModel):
    _name = "whatsapp.document.service"
    _description = "Shared WhatsApp document helpers"

    @api.model
    def _whatsapp_get_param(self, key, default=False):
        return (
            self.env["ir.config_parameter"].sudo().get_param(key, default)
        )

    @api.model
    def _whatsapp_validate_partner_mobile(self, partner):
        mobile = ""
        if partner:
            mobile = (partner.phone or partner.mobile or "").strip()
        try:
            return tools.validate_e164_or_raise(mobile, "sale order partner")
        except ValueError as e:
            raise ValidationError(_(str(e)))

    @api.model
    def _whatsapp_render_text(self, template_xmlid, record):
        """Renderiza mail.template -> texto plano. No revienta si falta.

        Usa el idioma del partner (no el del usuario) para que el mensaje
        llegue en el idioma del cliente cuando haya traducción.
        """
        try:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
        except Exception:
            template = False
        if not template:
            _logger.warning("WhatsApp template %s not found", template_xmlid)
            return ""
        if template.lang:
            _logger.warning(
                "WhatsApp template %s has fixed lang=%r: it overrides the "
                "partner language. Leave Idioma empty for partner-language "
                "rendering.", template_xmlid, template.lang)
        partner_lang = getattr(record.partner_id, "lang", False) \
            or self.env.lang
        try:
            values = (
                self.env["mail.template"]
                .with_context(tpl_partners_only=True, lang=partner_lang)
                .browse(template.id)
                ._generate_template([record.id], render_fields=["body_html"])
            )
            body_html = values.get(record.id, {}).pop("body_html", "") or ""
            return html2text.html2text(body_html)
        except Exception as e:
            _logger.exception("Error rendering WhatsApp template: %s", e)
            return ""

    @api.model
    def _whatsapp_create_pdf_attachment(
        self, record, report_xmlid, filename, res_model
    ):
        """Genera el PDF y lo devuelve como ir.attachment, o None si falla.

        Nunca deja `report` indefinido (bug anterior en account_move).
        El `store_fname` lo calcula Odoo a partir de `datas`.
        """
        try:
            report_content, _ext = self.env["ir.actions.report"]._render_qweb_pdf(
                report_xmlid, record.id
            )
        except Exception as e:
            _logger.exception("Could not render PDF %s: %s", report_xmlid, e)
            return False
        if not report_content:
            _logger.warning("Empty PDF content for %s", report_xmlid)
            return False
        return (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": filename,
                    "type": "binary",
                    "datas": base64.b64encode(report_content),
                    "mimetype": "application/pdf",
                    "res_model": res_model,
                    "res_id": record.id,
                }
            )
        )

    @api.model
    def _whatsapp_document_action(self, record, template_xmlid, report_xmlid,
                                  filename, res_model):
        """Valida, renderiza y genera el PDF, devolviendo la acción del wizard."""
        self._whatsapp_validate_partner_mobile(record.partner_id)
        warnings = []
        message = self._whatsapp_render_text(template_xmlid, record)
        if not message:
            warnings.append(_(
                "No se pudo renderizar la plantilla; revise el mensaje antes "
                "de enviar."))
        attachment = self._whatsapp_create_pdf_attachment(
            record, report_xmlid, filename, res_model)
        if not attachment:
            warnings.append(_(
                "No se pudo generar el PDF; el mensaje se enviará sin "
                "adjunto."))
        return self._whatsapp_build_wizard_action(
            message, attachment.id if attachment else False,
            warning="\n".join(warnings))

    @api.model
    def _whatsapp_build_wizard_action(self, message, attachment_id=False,
                                      warning=False):
        ctx = {"default_whatsapp_message": message or ""}
        if warning:
            ctx["default_warning_message"] = warning
        if attachment_id:
            ctx["default_attachment_ids"] = [(6, 0, [attachment_id])]
        return {
            "type": "ir.actions.act_window",
            "name": _("Whatsapp Message"),
            "res_model": "send.whatsapp.message",
            "target": "new",
            "view_mode": "form",
            "context": ctx,
        }
