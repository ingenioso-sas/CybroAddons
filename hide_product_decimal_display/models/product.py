from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qty_available = fields.Float(
        string='Quantity',
        required=True,
        digits=('Product Qty Display Only')
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    qty_available = fields.Float(
        string='Quantity',
        required=True,
        digits=('Product Qty Display Only')
    )