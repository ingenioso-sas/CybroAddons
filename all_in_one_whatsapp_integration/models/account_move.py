# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (Contact : odoo@cybrosys.com)
#
#    This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU AFFERO GENERAL PUBLIC LICENSE for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import models


class AccountMove(models.Model):
    """Inherited the module for adding a button that helps to send WhatsApp
    message to the customer. """
    _inherit = 'account.move'

    def action_send_by_whatsapp(self):
        """Open wizard with rendered message + PDF. Never leaves `report`
        undefined (previous UnboundLocalError)."""
        self.ensure_one()
        service = self.env["whatsapp.document.service"]
        service._whatsapp_validate_partner_mobile(self.partner_id)
        service._whatsapp_validate_twilio_config()
        message = service._whatsapp_render_text(
            "all_in_one_whatsapp_integration.account_move_whatsapp_template",
            self,
        )
        attachment = service._whatsapp_create_pdf_attachment(
            self, "account.account_invoices", "Invoice Report", "account.move"
        )
        return service._whatsapp_build_wizard_action(
            message, attachment.id if attachment else False
        )
