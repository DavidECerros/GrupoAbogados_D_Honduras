# Respaldos y recuperación

## Copias

Al comenzar actividad autenticada de cada día, se guarda una copia consistente
mediante la API de respaldo de SQLite. Incluye base de datos, configuración,
usuarios, historial, logos y PDFs. Conserva 30 copias diarias. Las copias manuales
se mantienen hasta que el administrador las gestione fuera de la aplicación.
El superusuario puede crear y descargar copias desde Configuración.

El destino inicial es `backups` dentro de la carpeta de datos. Puede cambiarse a
una ruta absoluta externa del equipo principal. Verifique que el destino siga
disponible al comenzar el día; si no se puede crear la copia, la operación no
continúa hasta corregir el almacenamiento. Para memoria estable, los checksums
se calculan leyendo los archivos por bloques.

Una copia contiene datos financieros y hashes de autenticación. Manténgala bajo
control del administrador. Un respaldo en el mismo disco no cubre su pérdida.

Cada ZIP tiene un manifiesto de versión y hashes SHA-256. La validación detecta
alteraciones y corrupción accidental; no constituye una firma digital. No restaure
archivos cuyo origen no sea confiable.

## Restauración desde la aplicación

1. Ingrese como superusuario y termine los cobros en curso.
2. En Configuración, use Cerrar otras sesiones y confirme con los operadores que
   hayan terminado. La restauración requiere que quede solamente su sesión.
3. Seleccione el ZIP, escriba RESTAURAR y marque la confirmación.
4. El sistema valida manifiesto, versión, integridad SQLite, claves foráneas y
   superusuario único. Antes de reemplazar datos crea una copia manual previa.
5. Durante la restauración bloquea nuevas operaciones. Si el reemplazo de base o
   carpetas falla, intenta revertir ambos al estado anterior y devuelve un error.
6. Se cierran las sesiones y se registra el evento en la base restaurada. Ingrese
   con las credenciales contenidas en esa copia y compruebe clientes, saldos y recibos.

No descomprima manualmente una base sobre un servidor activo. No reemplace SQLite
ignorando sus archivos WAL ni abra la base desde dos instalaciones a la vez.
Si falla el disco o el proceso durante una restauración, conserve todos los archivos
y la copia previa antes de intervenir; restaure desde una instalación detenida.

## Recuperar el superusuario

La recuperación se hace mediante un procedimiento local, sin ruta pública:

1. Cierre el servidor. El script comprueba que el puerto 8000 no esté abierto.
   Para otro puerto defina `GESTOR_RECOVERY_PORT` antes de ejecutar.
2. Abra `RecuperarSuperusuario.cmd` en el equipo principal, con acceso administrativo
   a la carpeta de datos. Si cambió `GESTOR_DATA_DIR`, conserve ese valor.
3. Ingrese dos veces una nueva contraseña de al menos 12 caracteres y el motivo.
   La contraseña se introduce sin mostrarse ni guardarse como texto legible.
4. El script cambia el hash Argon2id, quita el bloqueo, revoca todas las sesiones y
   registra motivo, cuenta y hora. Exige cambio de contraseña en el siguiente ingreso.
5. Inicie nuevamente mediante `Iniciar.cmd`.

La recuperación no crea un segundo superusuario y no borra movimientos ni auditoría.
