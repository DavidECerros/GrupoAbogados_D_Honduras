# Arquitectura y decisiones de implementación

Frontend React/Vite, API FastAPI y SQLite local. Un solo proceso sirve interfaz y
API desde el mismo origen. La compilación no utiliza CDN. El lanzador habilita
loopback por defecto y requiere TLS explícito para LAN.

## Modelo y transacciones

`backend/schema.sql` crea el esquema 1 de forma idempotente. Las claves foráneas
compuestas impiden que clientes, lotes y contratos pertenezcan a entidades distintas.
Índices únicos parciales impiden un segundo superusuario, una segunda reserva
activa y un segundo contrato activo por lote. Las cantidades monetarias se
almacenan en centavos y se validan en el servidor; la tasa usa seis decimales.

Cada solicitud autenticada vuelve a validar el estado y los permisos del usuario.
El proceso tiene una compuerta de solicitudes para serializar acceso y detener
operaciones durante respaldo/restauración. SQLite usa WAL, foreign keys y
BEGIN IMMEDIATE. No ejecutar varios workers ni varias instancias sobre los mismos
datos. El bloqueo y timeout de SQLite acotan esperas de escritura externa.

Pago, aplicaciones, saldo, consecutivo, instantánea de recibo y auditoría se
confirman juntos. El PDF se intenta después del commit financiero. El identificador
de operación y una huella de la solicitud permiten reintentos sin duplicación;
reutilizarlo con otros datos se rechaza. La identidad del operador siempre proviene
de la sesión. El commit de las dependencias se completa antes de enviar respuesta.

Una cesión conserva propietario histórico en pagos e instantáneas. La modificación
guarda versión con cuotas anteriores, preserva aplicaciones y reestructura el saldo
pendiente. La anulación invierte las aplicaciones originales y conserva la operación.

## Autenticación y permisos

Argon2id con salt individual y 19 MiB de memoria por verificación. Cookies HttpOnly,
SameSite Strict y Secure en HTTPS; tokens aleatorios cuyo hash se guarda en SQLite.
CSRF por sesión para mutaciones y validación de origen. Bloqueo por cuenta a los
cinco fallos durante 15 minutos y límite de intentos por origen. La auditoría omite
secretos; los errores de validación no devuelven valores de contraseñas ni tokens.

Los eventos de administración de entidades se registran a nivel instalación y
conservan el ID del registro aun si una entidad vacía se elimina. Los eventos
financieros conservan la asociación a la entidad, que impide su eliminación.
Los triggers rechazan UPDATE y DELETE de auditoría. No hay eliminación de usuarios
desde la API. Revocar permisos no borra el historial.

## Archivos y configuración

`GESTOR_DATA_DIR` define almacenamiento externo al programa. Recibos en
`recibos/ID_ENTIDAD/AÑO/MES/REC-AÑO-NÚMERO.pdf`. Logos con nombres derivados de
hash para conservar los que aparecen en recibos históricos. Los archivos
financieros se entregan por rutas autenticadas, sin carpetas públicas.

La zona horaria de operación es configurable, inicialmente America/Tegucigalpa.
La fecha de pago y el instante UTC de registro se conservan por separado. Cambios
de configuración se auditan. El frontend consulta la fecha del servidor para
actualizar alertas; estas consultas pasivas no extienden la sesión.

Las dependencias se fijan en lockfiles y el paquete portable incluye runtime,
dependencias, fuente del backend y frontend compilado. No incluye ninguna base,
credencial o documento del usuario.
