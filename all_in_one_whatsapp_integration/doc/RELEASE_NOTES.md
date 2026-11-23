# Release Notes

## 19.0.1.3.1 — 2026-11-23

### Proveedores
- En Ajustes → WhatsApp → *Canales habilitados* se muestran también los
  canales deshabilitados (``active_test=False``), de modo que se pueden
  activar desde esa misma lista.
- Probar un canal deshabilitado muestra un aviso amigable (notificación de
  advertencia) en lugar de un error técnico RPC. No se registra como prueba
  fallida porque no se intenta ningún envío.
- La prueba de conexión y los proveedores por defecto se limitan a la
  compañía actual, evitando usar registros de otra compañía.

## 19.0.1.3.0 — 2026-11-17

### Mantenimiento
- Se elimina la dependencia Python ``html2text``. La conversión de HTML a
  texto usa ``odoo.tools.html2plaintext`` (incluido en Odoo), adaptada para
  conservar los saltos de línea de ``div``/``li`` de las plantillas y los
  enlaces como referencias.
- El módulo ya no declara **ninguna** dependencia Python externa ni
  requiere ``pip install``.
- Nuevo test de la conversión HTML → texto de WhatsApp.

## 19.0.1.2.0 — 2026-11-17

### Proveedores
- Twilio se envía con la **API REST oficial** mediante ``requests``, sin el
  SDK ``twilio``. El módulo ya no exige `pip install twilio` para
  instalarse o actualizarse, y el canal funciona en cualquier entorno.
- Los medios se envían como claves ``MediaUrl`` repetidas (máximo 10) y el
  ``sid`` de la respuesta se conserva como ID de mensaje.
- Los errores HTTP se clasifican igual que en Cloud API/Evolution: 4xx
  permanente (salvo 408/429) y 5xx reintentable.
- Nuevo test de manifiesto que impide reintroducir ``twilio`` como
  dependencia Python.

## 19.0.1.1.1 — 2026-11-09

### Proveedores
- El formulario de proveedor muestra los **valores efectivos** de las
  credenciales y su origen: Global, Proveedor o Mixta.
- Botones para copiar las credenciales globales al proveedor o vaciar sus
  campos y volver al fallback de Ajustes → WhatsApp.
- Mensaje más claro cuando Evolution API devuelve «Connection Closed»:
  indica que la instancia perdió la conexión y debe reconectarse.

## 19.0.1.0.2 — 2026-11-08

### Seguridad
- Verificación obligatoria `X-Hub-Signature-256` en el webhook POST.
- Validación de `phone_number_id` y deduplicación por `wamid`.
- Grupos propios de Operador/Administrador y record rules por compañía.
- Credenciales por proveedor/compañía con fallback a ajustes globales.
- Webhook y cola endurecidos: sin eco de mensajes entrantes, sin
  reenvío de mensajes de contacto.

### Funcional
- Cola con backoff exponencial, errores permanentes 4xx, último/próximo
  intento e ID de mensaje del proveedor.
- Soporte de plantillas de WhatsApp en Cloud API.
- Envío de múltiples adjuntos en Cloud/Evolution y medios en Twilio.
- Validación E.164 en inbound y wizard; soporte de `phone`/`mobile`.
- Canales de Discuss visibles para el grupo configurado (inbox).
- Avisos de PDF/plantilla y notificación de fallos en el documento origen.
- Limpieza automática de cola y adjuntos antiguos.

### Mantenimiento
- Graph API configurable (por defecto `v27.0`).
- Eliminación de código/campos legacy y del XML ruidoso de limpieza.
- Migración `19.0.1.0.2` para normalizar datos y crear proveedores por
  compañía.
- Pruebas de proveedores, webhook/anti-eco, permisos, multi-compañía,
  plantillas, adjuntos y limpieza.
