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
{
    'name': "All in one Whatsapp",
    'version': '17.0.4.0.0',
    'category': 'Extra Tools',
    'summary': """Send whatsapp messages to the partner""",
    'description': """ This module helps you to send a whatsapp message to your 
     partners that are in sale order, purchase order, invoice and bills, and
     deliver orders.""",
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['base', 'web', 'sale', 'stock', 'purchase', 'account',
                'contacts', ],
    'data': [
        'security/ir.model.access.csv',
        'data/cleanup_legacy.xml',
        'data/whatsapp_provider_data.xml',
        'data/account_move_data.xml',
        'data/purchase_order_data.xml',
        'data/sale_order_data.xml',
        'data/stock_picking_data.xml',
        'data/cron.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/account_move_views.xml',
        'views/mail_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/mail_channel_views.xml',
        'wizard/send_whatsapp_message_views.xml',
        'views/whatsapp_provider_views.xml',
        'views/whatsapp_queue_message_views.xml',
        'views/whatsapp_queue_message_menu.xml',
    ],
    'external_dependencies': {
        'python': ['twilio','html2text'],
    },
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
