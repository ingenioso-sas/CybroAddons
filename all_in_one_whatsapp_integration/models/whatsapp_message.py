# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WhatsappMessage(models.Model):
    _name = 'whatsapp.message'
    _description = 'WhatsApp Message Queue'
    _order = 'create_date desc'

    number = fields.Char(string='Recipient', required=True, index=True)
    message = fields.Text(string='Message')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ], string='Status', default='draft', index=True)

    attachment_ids = fields.Many2many(
        'ir.attachment', string='Attachments',
        ondelete='restrict')

    def send_whatsapp_message(self, raise_on_error=True):
        """Sends the WhatsApp message using Cloud API.

        Desde cron usar raise_on_error=False (vía process_whatsapp_queue)
        para no abortar el lote.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        bearer_token = ICP.get_param(
            'all_in_one_whatsapp_integration.bearer_token')
        whatsapp_no = ICP.get_param(
            'all_in_one_whatsapp_integration.whatsapp_no')
        cloud_enabled = ICP.get_param(
            'all_in_one_whatsapp_integration.cloud_api_enabled')

        if not cloud_enabled:
            msg = _("Cloud API is disabled in Settings.")
            self.status = 'failed'
            if raise_on_error:
                raise UserError(msg)
            _logger.warning("%s", msg)
            return False
        if not bearer_token or not whatsapp_no:
            msg = _("WhatsApp configuration is missing. Please configure "
                    "the access token and phone number ID in the settings.")
            self.status = 'failed'
            if raise_on_error:
                raise UserError(msg)
            _logger.warning("%s", msg)
            return False

        import http.client
        conn = http.client.HTTPSConnection("graph.facebook.com", timeout=30)
        try:
            payload = json.dumps({
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": self.number,
                "type": "text",
                "text": {"preview_url": False, "body": self.message or ""},
            })
            headers = {'Content-Type': 'application/json',
                       'Authorization': 'Bearer %s' % bearer_token}
            conn.request("POST", "/v17.0/%s/messages" % whatsapp_no,
                         payload, headers)
            response = conn.getresponse()
            data = response.read().decode("utf-8", "replace")
            if response.status in (200, 201):
                self.status = 'sent'
                return True
            self.status = 'failed'
            _logger.error("WhatsApp send failed: %s - %s",
                          response.status, data[:1000])
            if raise_on_error:
                raise UserError(
                    _("WhatsApp message sending failed: %s") % data[:500])
            return False
        except UserError:
            raise
        except Exception as e:
            self.status = 'failed'
            _logger.exception("Error sending WhatsApp message: %s", e)
            if raise_on_error:
                raise UserError(_("Error sending WhatsApp message: %s") % e)
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @api.model
    def process_whatsapp_queue(self, limit=5):
        """Called by ir.cron. Never raises, logs per-record errors."""
        pending = self.search([('status', '=', 'pending')], limit=limit)
        for message in pending:
            try:
                message.send_whatsapp_message(raise_on_error=False)
            except Exception as e:  # noqa: BLE001 - cron must continue
                _logger.exception("WhatsApp queue error id=%s: %s",
                                  message.id, e)
        return True
