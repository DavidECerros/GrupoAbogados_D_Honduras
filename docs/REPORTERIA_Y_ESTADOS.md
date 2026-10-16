# Reportería, estado de cuenta y cierre de contratos - v0.2.3

## Reportería

El superusuario encuentra Reportería en Administración. Seleccione una
lotificadora o todas, tipo de reporte y fechas opcionales. En contratos, pagos
y lotes también puede seleccionar el estado. Descargar Excel genera:

- Contratos: cliente, lote, precio, prima, monto según condiciones, saldo y estado.
- Pagos: fecha, folio, moneda recibida, importe recibido, moneda contractual,
  aplicado, tasa, método, referencia y anulación.
- Lotes: lotificadora, código, ubicación, área, precio fijo o por superficie,
  valor actual de nueva venta, moneda y disponibilidad. Incluye identificación
  de eliminados; puede filtrar disponibles, reservados, vendidos o eliminados.
- Finanzas: cobros registrados, anulados y netos del período; valor de contratos
  activos creados en el período; cartera pendiente y vencida actuales por
  lotificadora y moneda. No es un estado de utilidades: no hay registro de gastos.
- Cobros vencidos: prima/cuota, vencimiento, importe, pagado y pendiente, por
  contrato, cliente, lote y moneda. Solo obligaciones pendientes de contratos activos.
- Todos los datos operativos: agrega clientes, lotificadoras, cuotas y reservas.

Las fechas filtran creación de contratos, fecha del pago y vencimiento en mora.
Los lotes no se filtran por fecha. Los saldos y estados se consultan a la fecha
actual; el filtro no reconstruye una cartera histórica. Sin fechas se exporta
todo el período. Los importes Excel están en unidades monetarias, no centavos.
No se suman HNL y USD. Credenciales, sesiones y contraseñas no se exportan.
Para un respaldo íntegro use Base de datos -> Exportar base o Respaldos.

## Estado de cuenta y plan de pagos

En Contratos -> Estado de cuenta están Exportar PDF y Exportar Excel. Incluyen
cliente actual, documento, lote, lotificadora, moneda, versión, precio, prima,
saldo, calendario de obligaciones y cobros confirmados/anulados. La columna
Pagado refleja aplicaciones reales; escribir una prima no acredita su pago.
Los planes largos continúan en varias páginas con encabezados repetidos.
El Excel conserva importes numéricos y fechas ordenables, con dos hojas:
Estado y plan de pagos y Cobros.

Cambiar el precio de un lote aplica a nuevas ventas. Un contrato existente
conserva sus condiciones hasta que el superusuario use Modificar condiciones;
esa operación guarda una versión anterior y respeta los cobros aplicados.

## Estados de contrato

- Pendiente de cancelar: existe saldo pendiente, calculado automáticamente.
- Cancelado (pagado): saldo cero; no equivale a anular el contrato.
- Pendiente de escriturar: con saldo cero, el superusuario marca este trámite.
- Escriturado: con saldo cero, el superusuario registra que terminó el trámite.
- Anulado: contrato retirado mediante la acción de anulación, conservando historial.

Estado de escritura se habilita en el estado de cuenta con saldo cero y pide
motivo y confirmación. Cada cambio queda auditado. Si una corrección de cobro
reabre saldo, vuelve a mostrarse Pendiente de cancelar. El dato de escritura
registrado permanece en la base y auditoría. No se genera ni inscribe una escritura.

## Resumen diario

Neto de hoy suma cobros confirmados cuya fecha de pago sea hoy, según la zona
horaria de la instalación. Excluye cobros anulados y separa HNL de USD. Debajo
se mantiene el neto del mes seleccionado; la gráfica sigue siendo mensual.

## Eliminación definitiva y reutilización de códigos

Eliminar conserva registros recuperables y reserva sus códigos/documentos.
Para corregir uno con historial, muestre Eliminados / anulados, restáurelo y edite.
Para un registro de prueba o erróneo sin referencias:

1. Elimine el lote o cliente.
2. Cambie Mostrar registros a Eliminados / anulados.
3. Use Eliminar definitivamente, indique motivo y confirme.
4. Cree de nuevo LM-001, u otro código, en la misma lotificadora.

La depuración borra la fila de la base y libera el código/documento, con respaldo
previo y auditoría. No borra contratos, reservas, cobros ni planos relacionados:
si los hay, devuelve las tablas que impiden depurar. No se reutiliza el ID del
registro depurado. Recuperarlo requiere restaurar un respaldo completo; no hay
botón Restaurar para una fila borrada definitivamente.

Precio fijo, su moneda y cambio de modalidad de un lote existente son exclusivos
del superusuario. Otros usuarios con permiso de edición pueden modificar datos
descriptivos, pero no alterar esas condiciones ni sustituir el precio fijo al vender.

## Autorizaciones

Un usuario puede solicitar anulación de un cobro propio, liberación de una reserva,
cesión de contrato o modificación de condiciones. La solicitud incluye registro,
datos propuestos y motivo. El superusuario revisa, aprueba o rechaza. Aprobar
ejecuta la operación con las mismas validaciones financieras; rechazar conserva
el estado original. Se registra solicitante, resolución, responsable y fecha.
El superusuario también puede ejecutar directamente sus acciones autorizadas.

## Actualizar en Windows

Cree respaldo, cierre el servidor anterior con Detener.cmd y extraiga v0.2.3
en otra carpeta. Ejecute su Iniciar.cmd y presione Ctrl+F5. La base externa
se conserva y migra al esquema 6; no copie una base vacía sobre sus datos.

El cobro y las exportaciones incluyen los meses/cuotas aplicados. Consulte
[pagos por mes](PAGOS_POR_MES.md) para excedentes, abonos parciales y modificación
del calendario conservando sus cuotas y aplicaciones.
