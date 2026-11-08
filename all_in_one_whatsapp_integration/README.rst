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
* Reintento: si un envío falla, el mensaje permanece *Pendiente* y el cron
  lo reintenta automáticamente con backoff exponencial hasta el tope de
  *Reintentos máximos*. Al agotarlo pasa a *Error* y puede reencolarse con
  el botón *Reintentar* (Ajustes > Técnico > WhatsApp > Cola de mensajes).
* Los errores 4xx no recuperables (excepto 408/429) se marcan como
  *Fallo permanente* y no se reintentan solos.
* Un fallo del servicio en modo *Enviar ahora* (Cloud/Evolution) también
  deja el mensaje en la cola para reintentarlo, en lugar de perderlo.
* Prueba de conexión: botones por proveedor en Ajustes > WhatsApp.

Seguridad y permisos
====================
* El webhook POST exige ``X-Hub-Signature-256`` calculado con el
  *Meta App Secret* (Ajustes > WhatsApp > Webhook). Sin ese secreto el
  endpoint rechaza todas las peticiones.
* Se valida el ``phone_number_id`` contra el configurado y se deduplican
  los mensajes por ``wamid``.
* Grupos propios: *WhatsApp / Operador* (envío y cola) y
  *WhatsApp / Administrador* (proveedores, credenciales y ajustes).
* Las credenciales pueden definirse por proveedor/compañía; si quedan
  vacías se usan los parámetros globales de Ajustes.
* Los registros de cola y proveedores se filtran por compañía.

Proveedores y adjuntos
======================
* Cloud API y Evolution API soportan varios adjuntos (se envía uno por
  mensaje). Twilio soporta medios vía ``media_url``. WhatsApp Web no
  permite adjuntar archivos automáticamente: el wizard lo advierte.
* Cloud API usa por defecto Graph API ``v27.0`` (configurable). Para
  mensajes iniciados por la empresa fuera de la ventana de 24 h se debe
  usar una plantilla aprobada (campos *Plantilla* de la cola).
* El espejo de Discuss solo reenvía mensajes escritos por usuarios
  internos; los mensajes entrantes del webhook nunca se reenvían.

API de integración
==================
* Consentimiento y número en el partner:

  * ``res.partner.whatsapp_opt_in`` y ``whatsapp_opt_in_date`` (pestaña
    *WhatsApp* de la ficha).
  * ``partner._get_whatsapp_number()``: número E.164 válido o vacío.
  * ``partner._get_whatsapp_recipient()``: contacto con consentimiento o
    partner comercial.
  * ``partner._can_send_whatsapp()``: consentimiento + número válido.

* ``whatsapp.provider.get_default_for_company(company, code=None)``:
  proveedor por defecto de la compañía, priorizando Cloud/Evolution.

* ``whatsapp.message.service.send_to_partner(partner, body, ...)`` y
  ``send_to_number(phone, body, ...)``: API de alto nivel que resuelve
  número, consentimiento, proveedor y cola/envío directo. Devuelve un
  diccionario con ``sent``, ``queue``, ``provider``, ``phone`` y ``reason``.

* ``whatsapp.tools.mask_number(phone)``: enmascarado para auditoría.

Los módulos de negocio deben usar esta API en lugar de replicar la
selección de proveedor o el branching cola/directo.

Retención y mantenimiento
=========================
* Un cron diario purga los enviados antiguos según *Retención de enviados*
  y los errores antiguos. La generación de PDFs y adjuntos también se
  limpia cuando corresponde.
* Las vistas de la cola incluyen filtros por estado, reintentos, fallos
  permanentes, adjuntos, documento relacionado, compañía y fecha.
