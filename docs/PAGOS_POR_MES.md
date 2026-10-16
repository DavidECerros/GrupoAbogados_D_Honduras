# Cobros por mes y modificación del plan - v0.2.3

## Elegir el mes que se paga

En Cobros y recibos -> Registrar cobro, seleccione contrato, importe y Mes / cuota
que está pagando. El desplegable usa las cuotas pendientes de ese contrato,
su vencimiento y el saldo de cada una. Prima es una opción separada cuando esté
pendiente. Automático conserva el orden: prima y luego las cuotas más antiguas.

La vista previa muestra el reparto antes de confirmar. Ejemplo con cuotas de
HNL 2,000: HNL 2,500 cubre la primera y abona HNL 500 a la siguiente, que conserva
HNL 1,500 pendiente. Un cobro inferior queda como abono parcial. Si la cuota ya
tiene un abono, solo se completa su saldo pendiente antes de continuar con otra.
HNL y USD se convierten con la tasa configurada y se redondean en el servidor.

Elegir una cuota posterior deja pendientes las anteriores; el formulario muestra
ese importe. No se acepta un cobro mayor que el saldo de la cuota seleccionada
y las siguientes. Actualizar cuotas y aplicación permite revisar datos nuevos.
Si otro cobro o cambio altera el reparto mostrado, se pide actualizar la vista
previa antes de confirmar.

## Recibos y reportes

Cada cobro genera un folio y un recibo con desglose de todos los meses/cuotas
que cubre, importes aplicados y saldo por cuota inmediatamente después del cobro.
Los abonos parciales se identifican. Fecha de pago y mes al que se aplica son
datos distintos: puede pagar en octubre una cuota de noviembre.

El desglose también está en el listado de cobros, estado de cuenta, PDF/Excel
del contrato, Reportería y exportación Mis pagos. Los Excel de Reportería para
pagos/finanzas y Mis pagos incluyen Aplicaciones por mes, con una fila por cuota,
folio, contrato, lote, moneda, aplicado y estado del cobro. Mis pagos conserva
el límite de acceso a cobros propios y expresa importes en unidades monetarias.
Los cobros anulados conservan su detalle identificado como anulado.

Los recibos nuevos conservan los meses originales aunque después se cambien
las fechas del contrato. En recibos anteriores se reconstruye el desglose con
las aplicaciones disponibles; puede no existir el saldo histórico exacto de
cada cuota al momento del cobro. No se inventa ese dato.

## Cambiar condiciones conservando las cuotas

Modificar condiciones actualiza fechas e importes en las cuotas existentes.
Conserva los identificadores y los pagos aplicados. No pone las cuotas pendientes
en cero para crear un calendario completo adicional.

Número total de cuotas del contrato incluye las pagadas. Por ejemplo, con 120
cuotas y dos ya pagadas, mantener 120 deja 118 pendientes. Solo se agregan filas
si aumenta el número total. Al reducirlo, no se permite retirar cuotas que tengan
pagos vigentes. Las cuotas completamente pagadas mantienen su importe; los
abonos parciales se respetan y el saldo se distribuye en las cuotas restantes.

El vencimiento de la primera cuota corresponde al plan completo. Sus siguientes
fechas se calculan mensualmente, ajustándose al último día de meses más cortos.
Se conservan los recibos y versiones anteriores.

Enviar este cambio a Autorizaciones queda marcado por defecto. La solicitud
no altera el contrato: el superusuario debe revisarla y aprobarla para aplicar
el cambio. Si se registra otro cobro o cambian condiciones mientras está pendiente,
se debe generar una solicitud actualizada. El superusuario puede desmarcar la
opción para aplicar directamente su cambio; los demás usuarios solicitan aprobación.

## Corregir un plan que ya muestra cuotas en cero y nuevas duplicadas

Tras actualizar, abra su estado de cuenta y Modificar condiciones. Revise el
número total correcto de cuotas, prima, precio y fechas; envíe y apruebe la
solicitud. Al aplicar el cambio se reorganizan las filas vigentes, conservando
pagos y recibos. Las filas históricas retiradas quedan fuera del plan vigente;
se conservan para auditoría y referencias de aplicaciones anteriores.
La actualización por sí sola no modifica condiciones ni cobros de la base real.

## Actualizar

Cree un respaldo, cierre la versión anterior con Detener.cmd, extraiga el paquete
Windows v0.2.3 en una carpeta nueva y abra Iniciar.cmd. Recargue con Ctrl+F5.
El esquema migra de versiones 1 a 5 al esquema 6 conservando la base externa.
