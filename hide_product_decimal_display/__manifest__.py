{
    'name': 'Clean Product Quantity Display',
    'version': '13.0.1.0.0',
    'summary': 'Muestra cantidades sin ceros decimales innecesarios',
    'author': 'IngeniosoSAS',
    'company': 'IngeniosoSAS',
    'website': 'https://www.ingenioso.co',
    'category': 'Extra Tools',
    'depends': ['sale', 'stock', 'base', 'product', 'purchase'],
    'data': [
        'views/sale_order_line.xml',
        'views/purchase_order_line.xml',
        'data/decimal_precision.xml',
    ],
    'installable': True,
    'auto_install': False,
}
