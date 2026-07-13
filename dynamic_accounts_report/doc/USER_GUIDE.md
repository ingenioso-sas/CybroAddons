# Manual de Usuario: Auditoría Financiera y Panel de Anomalías

Este manual le explica cómo utilizar el botón de **Auditoría de Cifras** en los reportes financieros dinámicos para verificar la consistencia contable de su empresa usando reglas tradicionales o análisis de Inteligencia Artificial (IA).

---

## 1. ¿Cómo utilizar la Auditoría de Cifras?

En cualquier reporte financiero dinámico (como *Trial Balance*, *General Ledger*, *Partner Ledger*, etc.), siga estos sencillos pasos:

1. Abra el reporte contable deseado desde el menú **Dynamic Financial Reports**.
2. Aplique los filtros de fechas u otros parámetros y haga clic en **Apply**.
3. En la esquina superior izquierda del reporte, haga clic en el botón amarillo **Auditar Cifras**.
4. En el asistente emergente que se abre, usted podrá elegir el **Tipo de Análisis**:
   * **Análisis Estático (Reglas Contables)**: Analiza el reporte de forma inmediata usando reglas matemáticas y de partida doble programadas localmente.
   * **Análisis Inteligente con IA (LM-Studio)**: Envía de manera segura un resumen de las cifras del reporte a un modelo de lenguaje cargado en el servidor de LM-Studio para obtener un diagnóstico avanzado.

---

## 2. Requisitos para Habilitar el Análisis Inteligente con IA

El Análisis con IA estará deshabilitado o mostrará una advertencia si el administrador del sistema no ha configurado la conexión en Odoo. 

Si los parámetros de sistema no están configurados, al intentar seleccionar "Análisis Inteligente con IA", el sistema volverá automáticamente a "Análisis Estático" e indicará qué valores faltan.

### Parámetros que debe configurar el Administrador:
* `lm_studio.api_url`: URL del servidor LM-Studio (ej: `http://localhost:1234/v1`).
* `lm_studio.api_key`: Token o clave de acceso del servidor.

---

## 3. Tipos de Alertas y Explicaciones

Independientemente del tipo de análisis que elija, la herramienta clasificará las advertencias encontradas de la siguiente manera:

* **🔴 Alertas Críticas (Descuadres)**: Cuando los débitos totales no coinciden con los créditos o el balance general está descuadrado. Se sugiere auditar transacciones del periodo.
* **🟡 Advertencias (Saldos Invertidos)**: Cuentas bancarias o de caja en negativo, saldos a favor de clientes/anticipos sin aplicar, o saldos deudores con proveedores.
* **🛠️ Acciones de Corrección**: Cada anomalía incluye una guía clara que detalla los pasos sugeridos en Odoo para conciliar los valores o corregir los registros correspondientes.
