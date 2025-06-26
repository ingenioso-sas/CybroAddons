from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    PRODUCT_QTY_DISPLAY_ONLY = 'Product Qty Display Only'

    qty_available = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )

    virtual_available = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )
    sales_count = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )

    purchased_product_qty = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    PRODUCT_QTY_DISPLAY_ONLY = 'Product Qty Display Only'

    qty_available = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )
    
    virtual_available = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )
    sales_count = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )

    purchased_product_qty = fields.Float(
        string='Quantity',
        required=True,
        digits=('PRODUCT_QTY_DISPLAY_ONLY')
    )
