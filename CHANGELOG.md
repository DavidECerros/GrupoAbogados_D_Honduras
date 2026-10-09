# Registro de versiones

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
