
{
    'name': 'Hide Update Product Quantity',
    'summary': """Hide Botton update Product quantity Will be Visible Only for Specified Group""",
    'version': '13.0.1.0',
    'description': """Hide Botton update Product quantity Will be Visible Only for Specified Group""",
    'author': 'IngeniosoSAS',
    'company': 'IngeniosoSAS',
    'website': 'https://www.ingenioso.co',
    'category': 'Extra Tools',
    'depends': ['base', 'product', 'stock'],
    'license': 'AGPL-3',
    'data': [
        'security/view_product_quantity.xml',
        'views/hide_product_quantity.xml'
    ],
    'images': ['static/description/banner.jpg'],
    'demo': [],
    'installable': True,
    'auto_install': False,

}
