# Registro de versiones

## 0.2.1 — 14 de octubre de 2026

- Tarifas por m², vara² y moneda independientes por lotificadora, editables solo
  por el superusuario desde Configuración o Lotificadoras. Migración que conserva
  la tarifa anterior una sola vez y no recalcula contratos existentes.
- Precio fijo y cálculo por superficie diferenciados en el formulario de lote;
  el valor manual deja de mostrarse como editable mientras se usa una tarifa.
- Desglose explícito del precio total menos prima en Nueva venta.
- Corrección del manejo de ventanas de formularios y validación visible de campos.
- Eliminación recuperable y restauración para clientes, lotes y planos; liberación
  y archivo de reservas, archivo de lotificadoras y desactivación de usuarios.
- Anulación/reactivación de contratos con comprobación de cobros y disponibilidad.
  Los cobros se anulan conservando sus recibos e historial, sin borrado físico.
- Edición de reservas, datos de cobros y motivos de solicitudes pendientes.
- Confirmación, motivo, respaldo previo y auditoría para bajas/restauraciones.
- Esquema 4 y restauración de respaldos anteriores. 86 pruebas de backend,
  Ruff, ESLint y compilación de producción; edición repetida, borrado/restauración,
  precio fijo con prima y tarifas independientes comprobados en navegador.

## 0.2.0 — 14 de octubre de 2026

- Áreas de lotes en m² y varas², selección de unidad de venta y tarifas por
  superficie exclusivas del superusuario junto a la configuración del dólar.
- Cotización contractual validada en el servidor, con detección de cambios y
  conservación de área, factor, tarifa y moneda de la venta.
- Roles Administrador y Usuario estándar; diez módulos identificados con acceso
  desactivado, consulta o edición y autorización en cada solicitud de la API.
- Planos con coordenadas locales/GPS/UTM, rumbos y distancias, revisión geométrica,
  reunión de polígonos contiguos, PDF a escala y exportación GeoJSON.
- Formato de reunión con título fijo, calle/avenida, cuadro de colindancias,
  datos profesionales y propietario consultado desde el contrato del lote.
- Resumen primero, seguido por clientes, lotes, reservas, contratos, cobros,
  morosidad, planos, historial y autorizaciones.
- Mapa de Honduras con OpenStreetMap por internet, opcional y con atribución.
- Esquema 3 y restauración compatible con respaldos de versiones anteriores.
- Plantilla y exportación de lotes ampliadas sin rechazar archivos anteriores.
- Validación: 75 pruebas, Ruff, ESLint, compilación y comprobaciones en navegador.

## 0.1.3 — 8 de octubre de 2026

- Inicio del servidor en segundo plano, apertura del navegador cuando responde
  y reutilizacion del proceso al abrir el acceso directo varias veces.
- `Detener.cmd` para cierre controlado e `IniciarConsola.cmd` para diagnostico.
- Registros y PID fuera del codigo; aviso si otra instalacion ocupa el puerto.
- Estado del servidor informa la version real de la aplicacion.
- Validacion: 55 pruebas de backend, Ruff y compilacion de produccion.
  Inicio oculto, reutilizacion del PID y cierre controlado comprobados en Windows.

## 0.1.2 — 8 de octubre de 2026

- Importación Excel y CSV de clientes y lotes con vista previa, errores por fila,
  creación o actualización, respaldo previo y auditoría.
- Exportación de ambos catálogos y plantillas Excel descargables con instrucciones.
- Panel Base de datos exclusivo del superusuario: tablas, columnas, consulta SQL,
  vista previa de modificaciones, ejecución confirmada y exportación SQLite.
- Traslado de la carpeta de datos con copia previa, conservación del original,
  configuración de la nueva ruta y pausa hasta reiniciar el servidor.
- Documentación de administración de datos y alternativas de alojamiento online.
- Validación: 55 pruebas de backend, Ruff, ESLint y compilación de producción.
  Importación y ejecución SQL verificadas en navegador con datos ficticios.

## 0.1.1 — 8 de octubre de 2026

- Inhabilitación y reactivación de clientes con filtros, permisos y auditoría.
- Migración del esquema 1 al 2, incluyendo restauración de respaldos anteriores.
- Formularios de modificación y cesión visibles directamente en el estado de cuenta.
- Ventana de versiones del contrato con consulta de las condiciones anteriores.
- Validación: 38 pruebas de backend y verificación de los flujos en navegador.

## 0.1.0 — 8 de octubre de 2026

- Primera versión funcional: autenticación, entidades, usuarios, clientes, lotes,
  reservas, contratos, cuotas, cobros y recibos PDF.
- Cesiones, modificaciones, autorizaciones, morosidad, auditoría y reportes Excel.
- Respaldo/restauración, recuperación local y paquete portable Windows.
- Validación: 34 pruebas de backend y medición con datos sintéticos de 10,000 lotes,
  100,000 pagos y cinco sesiones. Pendiente aceptación en Windows 10 objetivo.
