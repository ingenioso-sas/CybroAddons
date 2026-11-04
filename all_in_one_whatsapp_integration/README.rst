.. image:: https://img.shields.io/badge/license-AGPL--3-blue.svg
    :target: https://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3

All in one Whatsapp
===================
This module helps you to send a whatsapp message to your partners that are in sale order,
purchase order, invoice and bills, and deliver orders.

Installation
============
- www.odoo.com/documentation/16.0/setup/install.html
- pip install twilio

Company
-------
* `Cybrosys Techno Solutions <https://cybrosys.com/>`__

License
-------
Affero General Public License, Version 3 (AGPL v3).
(https://www.gnu.org/licenses/agpl-3.0-standalone.html)

Credits
-------
Developer: (V16)- Raneesha M K, Jumana Jabin MP, Vishnu P
Contact: odoo@cybrosys.com

Contacts
--------
* Mail Contact : odoo@cybrosys.com
* Website : https://cybrosys.com

Bug Tracker
-----------
Bugs are tracked on GitHub Issues. In case of trouble, please check there if your issue has already been reported.

Maintainer
==========
.. image:: https://cybrosys.com/images/logo.png
   :target: https://cybrosys.com

This module is maintained by Cybrosys Technologies.

For support and more information, please visit https://www.cybrosys.com

Further information
===================
HTML Description: `<static/description/index.html>`__

Cola única de WhatsApp
======================
* `whatsapp.queue.message` es la ÚNICA cola del módulo (el antiguo
  `whatsapp.message` fue eliminado). Guarda pendientes de Cloud API y
  Evolution API, con causa de fallo (`error_msg`) y reintentos.
* `whatsapp.provider` define los canales; solo los habilitados (`active`)
  aparecen en el wizard y los procesa el cron (cada 5').
* Entradas a la cola: wizard (opción *Encolar*), espejo de Discuss y
  `whatsapp.queue.message.create_queue_message()`.
* Reintento: botón *Reintentar* en los registros en estado *Error*
  (Ajustes > Técnico > WhatsApp > Cola de mensajes).
* Prueba de conexión: botones por proveedor en Ajustes > WhatsApp.
