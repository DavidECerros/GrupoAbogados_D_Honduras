# Evidencia de aceptación de la versión 0.1.2

Fecha de verificación: 8 de octubre de 2026. Los datos son sintéticos y están
aislados de la instalación de operación. El requerimiento fuente es la versión
1.0 del 29 de septiembre de 2026.

## Pruebas automatizadas

55 pruebas de backend pasan con pytest. Se verifica compilación de producción
de React/Vite, revisión ESLint y revisión Ruff del backend. Los casos financieros
usan valores en centavos, dos entidades y operadores separados.

La actualización verifica inhabilitación/reactivación de clientes, permisos,
filtros y migración del esquema anterior sin pérdida de registros. En el navegador
se probaron modificación de condiciones, consulta de versiones y cesión con datos
ficticios. Estos formularios ahora se muestran directamente en la ventana.

La versión 0.1.2 agrega 17 casos para importación Excel/CSV, exportación,
plantillas, permisos, vistas previas y ejecución SQL con respaldo, límites del
editor y traslado de datos con pausa y conservación de la carpeta original.

| Criterio | Evidencia |
| --- | --- |
| CA 01 | Superusuario único, rechazo de segundo inicio y de administración por operador. |
| CA 02 | Solicitud anónima, cierre de sesión, revocación por restablecimiento y expiración de sesión. |
| CA 03 | Aislamiento de clientes, descargas y operaciones por entidad; revocación inmediata. |
| CA 04 | Venta simultánea produce un contrato; cambios de precio base no alteran condiciones. |
| CA 05 | Precio 100,000 HNL mantiene saldo 100,000 antes de prima y 90,000 después de cobrar 10,000. |
| CA 06 | Pago de 15,000 cubre prima y cuota parcialmente; suma de aplicaciones coincide; ajuste de último centavo. |
| CA 07 | Pago HNL 2,500 a tasa 25 aplica USD 100 y conserva la tasa tras cambiar la configuración. |
| CA 08 | Reintento comparte ID/folio; cinco cobros concurrentes generan folios únicos y respetan saldo. |
| CA 09 | PDF se genera en ruta por entidad/año/mes; fallo simulado conserva pago y permite regeneración. |
| CA 10 | Operador solicita; superusuario aprueba; anulación restituye saldo y conserva evento. |
| CA 11 | Pago parcial conserva atraso; fronteras de semáforo hoy, 4 días, 30 y 31 días. |
| CA 12 | Cesión conserva instantánea, propietario de pagos y saldo completo. |
| CA 13 | Operador consulta su historial; superusuario conserva historial y totales globales. |
| CA 14 | PDF y Excel locales; respaldo restaura relaciones, clientes y saldo. ZIP alterado se rechaza; fallo de reemplazo revierte base y recibos. |
| CA 15 | Escenario de 10,000 lotes, 100,000 pagos y cinco sesiones medido; detalle en benchmark.json. |

Adicionales: validación monetaria, comprobante bancario, rechazo de operador
inyectado por formulario, protección CSRF, intentos fallidos persistidos, auditoría
inmutable, archivo de entidad, copia diaria y consultas pasivas que no renuevan
sesión. Reestructuración con pagos conserva aplicaciones y saldo aun después
de anular un pago anterior.

## Rendimiento medido

Equipo anfitrión Windows 11 AMD64; Python 3.13.3 en entorno de desarrollo.
Se crea una base descartable de 10,000 lotes y 100,000 pagos, inicia un backend
separado y hace las consultas con cinco sesiones autenticadas simultáneas.

| Consulta | Mayor latencia de cinco solicitudes |
| --- | ---: |
| Clientes, página 100 | 179 ms |
| Pagos, página 100 | 245 ms |
| Contratos, página 100 | 571 ms |
| Mora, página 100 | 1,601 ms |
| Dashboard | 1,918 ms |
| Confirmar cobro, incluyendo PDF | 385 ms |

Memoria residente del proceso del backend y su lanzador: 80.25 MB antes y
87.46 MB después. Se mide todo el árbol de procesos para evitar medir solo el
lanzador de Python. Excluye navegador y sistema operativo. La fase de creación
de datos sintéticos y las exportaciones no forman parte de la medición normal.

Las consultas medidas quedan por debajo del objetivo de 2 segundos y el cobro,
incluyendo PDF en esta prueba, por debajo de 3 segundos. No es una garantía:
la aceptación en Windows 10, con 4 GB RAM y SSD, sigue pendiente. El dashboard
tiene poco margen ante cargas mayores o un equipo más lento.

## Límites de esta evidencia

Se verificó el flujo de ingreso, dashboard y cobro en el navegador, con datos
sintéticos. Un pago de prima por 15,000 HNL generó un folio y redujo el saldo de
125,000 a 110,000 HNL. La pantalla de resumen se inspeccionó a 390 px de ancho.
El recibo carta se renderizó y se revisó visualmente; media carta se verifica en
las pruebas. El paquete con runtime propio arrancó y presentó configuración
inicial sin cuentas existentes.

- La operación local no depende de internet por diseño y el paquete incluye los
  recursos. Debe completarse la prueba física con internet desconectado en el equipo
  del despacho, así como impresión en su impresora.
- El flujo LAN requiere validar certificados, DNS, firewall y acceso móvil en la red real.
- Las cesiones se hacen efectivas hoy; no se programan cesiones futuras ni retroactivas.
- Restauraciones se probaron en bases sintéticas. La pérdida de energía durante
  restauración requiere recuperar desde la copia previa con el servidor detenido.
- El paquete no es un instalador MSI ni un servicio Windows. Incluye el runtime,
  un lanzador y un script opcional para crear el acceso directo.
- Antes de usar datos reales, el despacho debe revisar los recibos y las reglas
  de reestructuración, y hacer una restauración de prueba en su equipo.

Comandos reproducibles y código de evidencia: `tests/`, `scripts/benchmark.py`,
`docs/benchmark.json` y el flujo CI en `.github/workflows/ci.yml`.
