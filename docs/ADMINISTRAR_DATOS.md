# Administración de datos

Disponible para el superusuario desde **Base de datos**.

## Clientes y lotes

Cada sección tiene **Plantilla**, **Importar** y **Exportar Excel**. La exportación
incluye todas las páginas que coinciden con la búsqueda y el estado elegidos.
Para exportar clientes inhabilitados también, elija **Todos los clientes**.

Las plantillas incluyen una hoja de datos vacía y otra de instrucciones. Complete
la hoja Clientes o Lotes desde la fila 2 y conserve sus encabezados. Los ejemplos
ficticios de Instrucciones no se importan. Documentos y teléfonos son texto para
conservar ceros iniciales. Precio se ingresa en unidades monetarias, no centavos.

Puede cargar Excel .xlsx o CSV UTF-8 con los mismos encabezados. Se admiten hasta
10,000 registros y 12 MB. No se admiten fórmulas en la hoja de datos.

**Solo crear nuevos** rechaza registros existentes. **Crear y actualizar** usa ID
si lo incluye; de otro modo busca clientes por tipo de documento y documento,
y lotes por código, dentro de la lotificadora seleccionada. Los campos vacíos
opcionales reemplazan el contenido anterior al actualizar. Revise el archivo
antes de confirmar. El estado de los lotes depende de sus reservas y contratos:
la importación lo conserva. Cambiar el precio base de un lote no cambia ventas anteriores.

La vista previa muestra errores por fila. Si hay un error, no se importa ninguna
fila. Si el catálogo cambia después de revisar, debe repetir la vista previa.
Antes de guardar se crea un respaldo completo y cada fila se registra en auditoría.

## Editor SQL

Permite SELECT, INSERT, UPDATE y DELETE, una sentencia por operación. La vista
previa de una modificación se ejecuta y revierte: no guarda cambios. Para guardar,
escriba EJECUTAR y marque la confirmación. Se crea un respaldo antes de ejecutar.

Los importes internos de contratos, pagos, cuotas y lotes están en centavos:
100.00 se representa como 10000. El editor puede alterar los datos financieros
sin aplicar los cálculos de los formularios de cobro. Es responsabilidad del
superusuario mantener la coherencia entre cuotas, asignaciones, pagos y recibos.
Para operaciones habituales utilice los formularios del sistema.

Se conservan las restricciones y claves foráneas de SQLite. No se permite alterar
el esquema, editar la auditoría o sesiones, cambiar el versionado, abrir otras
bases, ejecutar PRAGMA ni cargar extensiones. Se conserva un superusuario activo.
Las consultas se limitan a cinco segundos y 200 resultados visibles. La vista
previa caduca a los diez minutos y se rechaza si cambiaron las tablas consultadas.

## Archivo principal, respaldo y traslado

El archivo principal es **gestor.sqlite3**. La pantalla muestra su ruta. Descargar
SQLite obtiene una copia consistente de todas las tablas. Esa copia incluye datos
de usuarios y sesiones: guárdela bajo control del administrador. No la publique.

El respaldo ZIP incluye también recibos y logos. Para recuperar la instalación
completa use **Importar o restaurar respaldo**, que lleva a Configuración. La copia
SQLite aislada no sustituye al ZIP cuando necesita conservar sus documentos.

**Mover carpeta de datos** copia base, logos, recibos y respaldos a una carpeta
vacía en un disco local del equipo principal. Cierre las demás sesiones antes.
Tras el traslado el sistema se pausa: termine el servidor con Ctrl+C y abra
Iniciar.cmd de la versión actual nuevamente. La carpeta original se conserva,
pero deja de recibir operaciones. Use siempre la carpeta nueva para respaldar.

La ubicación queda en `%LOCALAPPDATA%\GrupoAbogados_D_Honduras-location.json`, fuera
del programa. Actualizar el programa conserva esa configuración. Si utiliza
GESTOR_DATA_DIR, esa variable tiene prioridad y el traslado debe hacerse con el
servidor detenido, actualizando su valor. No utilice una carpeta de red o
sincronizada como ubicación de la base activa. Los ZIP de respaldo sí pueden
copiarse a otro disco o a almacenamiento remoto.
