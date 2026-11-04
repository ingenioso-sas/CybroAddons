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
from odoo import models


class PurchaseOrder(models.Model):
    """Inherited the module for adding a button that helps to send whatsapp
        message to the customer """
    _inherit = "purchase.order"

    def action_send_by_whatsapp(self):
        """ When you click the send_by_whatsapp button, it will open a wizard
        that contain the message to send to the whatsapp web page. """
        self.ensure_one()
        service = self.env["whatsapp.document.service"]
        service._whatsapp_validate_partner_mobile(self.partner_id)
        service._whatsapp_validate_twilio_config()
        message = service._whatsapp_render_text(
            "all_in_one_whatsapp_integration.purchase_order_whatsapp_template",
            self,
        )
        attachment = service._whatsapp_create_pdf_attachment(
            self,
            "purchase.action_report_purchase_order",
            "Purchase Report",
            "purchase.order",
        )
        return service._whatsapp_build_wizard_action(
            message, attachment.id if attachment else False
        )
