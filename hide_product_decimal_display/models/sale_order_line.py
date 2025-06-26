from odoo import models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_uom_qty = fields.Float(
        string='Quantity',
        required=True,
        digits=('Product Qty Display Only')
    )
