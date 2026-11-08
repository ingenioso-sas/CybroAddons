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
        """Open wizard with rendered message + PDF."""
        self.ensure_one()
        service = self.env["whatsapp.document.service"]
        return service._whatsapp_document_action(
            self,
            "all_in_one_whatsapp_integration.account_move_whatsapp_template",
            "account.account_invoices",
            "Invoice Report",
            "account.move",
        )
