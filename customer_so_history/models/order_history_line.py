# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import fields, models

class OrderHistoryLine(models.Model):
    """Represents a line item in the customer’s sales order history, including product details, pricing, and taxes."""
    _name = 'order.history.line'
    _description = 'Order History Line'

    order_id = fields.Many2one('sale.order',
        help="Reference to the sale order associated with this line.")
    name = fields.Char('Order',
        help="The name or reference of the sale order.")
    product_id = fields.Many2one('product.product',
        help="The product associated with this order line.")
    product_uom_qty = fields.Integer('Quantity',
        help="The quantity of the product ordered.")
    price_unit = fields.Integer('Unit Price',
        help="The unit price of the product at the time of the order.")
    tax_id = fields.Many2many('account.tax',
        help="The taxes applied to this order line.")
    company_id = fields.Many2one('res.company',
        default=lambda self: self.env.company,
        help="The company associated with this order line.")
    price_subtotal = fields.Integer(string='Subtotal',
        help="The total price for this order line, excluding taxes.")

    def action_add(self):
        """
        Creates a new sale order line with the current form data.

        This method collects the current values from the form (such as `order_id`,
        `product_id`, `product_uom_qty`, `price_unit`, `tax_id`, `price_subtotal`,
        and `company_id`) and creates a new record in the `sale.order.line` model.

        Fields Used:
        - order_id: The ID of the associated sale order.
        - product_id: The ID of the product being sold.
        - product_uom_qty: The quantity of the product in the specified unit of measure.
        - price_unit: The unit price of the product.
        - tax_id: The list of applicable taxes for the product.
        - price_subtotal: The subtotal price after calculating quantities and taxes.
        - company_id: The ID of the company for the sale order line.

        This method uses `sudo()` to bypass access restrictions and allows the creation
        of sale order lines even for users with limited permissions.

        """
        vals = {
            'order_id':self.order_id.id,
            'product_id':self.product_id.id,
            'product_uom_qty':self.product_uom_qty,
            'price_unit':self.price_unit,
            'tax_id': self.tax_id.ids,
            'price_subtotal': self.price_subtotal,
            'company_id': self.company_id.id,
        }
        self.env['sale.order.line'].sudo().create(vals)
