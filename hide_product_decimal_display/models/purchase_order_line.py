from odoo import models, fields


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_qty = fields.Float(
        string='Quantity',
        required=True,
        digits=('Product Qty Display Only')
    )