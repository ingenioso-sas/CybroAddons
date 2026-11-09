# Release Notes

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
