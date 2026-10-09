# Manual de operación

## Preparación

El superusuario crea lotificadoras, determina HNL o USD como moneda base y puede
subir un logo. Crea operadores y les asigna entidades. Los operadores deben cambiar
la contraseña temporal antes de usar el sistema. Cualquier revocación de una
entidad se aplica a las siguientes consultas y descargas, conservando el historial.

Use el selector superior para trabajar con la lotificadora correspondiente. Una
entidad archivada conserva sus datos para consulta y no admite nuevas operaciones.
Una entidad sin registros asociados puede eliminarse con el botón de eliminación;
las que tienen historial deben archivarse desde Editar.

## Clientes, lotes, reservas y ventas

1. En Clientes registre nombre, documento, teléfono y datos opcionales. El
   documento no se comparte entre lotificadoras. Los operadores pueden modificar
   contacto y observaciones, pero no la identidad de un cliente existente.
2. El superusuario crea los lotes, con código único por entidad, ubicación y precio
   base. Cambiar este precio no modifica ventas anteriores.
3. Puede reservar un lote disponible para un cliente. Una reserva vencida requiere
   revisión y liberación del superusuario; el operador puede solicitarla.
4. En Contratos cree la venta con cliente, lote, precio acordado, prima, fechas y
   número de cuotas. Confirme los datos antes de guardar.
5. La prima acordada sigue pendiente hasta recibir un pago. El saldo total inicial
   es el precio completo. Las cuotas mensuales financian precio menos prima,
   manteniendo el día de vencimiento o el último día disponible del mes.

No existen intereses ni recargos. Una venta al contado también debe liquidarse
mediante un pago registrado. Puede usar una prima igual al precio y una cuota
de importe cero; la prima se cobra por el flujo normal.

## Cobros

Busque por cliente, documento o lote, abra Cobrar y revise prima pendiente, cuotas
vencidas y saldo. Ingrese importe, moneda, fecha y método. Depósito y transferencia
requieren comprobante bancario. Confirme los datos mediante la casilla y registre.

Los pagos se aplican primero a la prima y después a cuotas por vencimiento,
admitiendo abonos parciales o anticipados. No se aceptan excedentes del saldo.
Para otra moneda, el superusuario debe haber configurado la tasa HNL por USD.
El servidor usa Decimal y redondea a centavos; la estimación de la pantalla es orientativa.

Un reintento en el mismo formulario conserva el identificador de operación. Si
ocurre una interrupción, consulte primero el listado de cobros. No abra una segunda
operación para el mismo dinero sin verificar si la primera se confirmó.

Al confirmar, descargue o abra el recibo para imprimir desde el navegador. El
folio es único por entidad y año, incluyendo recibos anulados. El recibo conserva
cliente, importes, tasa, operador y saldo del momento del cobro. No es factura fiscal.

Si falla el PDF, el pago queda confirmado y el mismo recibo queda pendiente. La
descarga vuelve a generarlo con el mismo folio; no debe registrar otro pago.
Los operadores solo pueden descargar sus propios recibos en entidades asignadas.

## Correcciones y autorizaciones

Los pagos no se editan ni se eliminan. El operador solicita anulación con motivo;
el superusuario aprueba o rechaza desde Autorizaciones. La anulación restituye
las aplicaciones y conserva responsables, importe, motivo y original.

Para cesión, abra el estado de cuenta y seleccione otro cliente de la misma
entidad. Se transfiere el saldo pendiente completo el día del registro. No se
admiten cesiones parciales, futuras o retroactivas. Los pagos y recibos anteriores
conservan a su propietario histórico. El operador solicita aprobación.

La modificación contractual exige motivo y conserva una versión completa de las
condiciones y cuotas anteriores. Con historial de pagos:

- El precio nuevo no puede ser inferior a los pagos válidos aplicados.
- La prima nueva debe cubrir lo ya aplicado a prima.
- Se conservan obligaciones pagadas y aplicaciones para una eventual anulación.
- La prima restante y el saldo a financiar se recalculan; el saldo a financiar se
  distribuye entre el número de nuevas cuotas pendientes indicado.
- La numeración de nuevas cuotas continúa tras las anteriores. Las cuotas
  anteriores sin saldo representan el historial de la reestructuración.
- Ningún recibo anterior cambia su instantánea. Anular un pago anterior devuelve
  su importe a la obligación histórica correspondiente, sin perder el saldo correcto.

## Mora y reportes

Verde: sin obligaciones vencidas ni próximas. Amarillo: una obligación vence hoy
o en los siguientes cuatro días. Rojo: existe deuda vencida; más de 30 días se
identifica como moroso. Un pago parcial no reinicia la fecha de atraso restante.
Se muestran deuda vencida y saldo total por separado, sin sumar HNL y USD.
Las alertas se consultan al entrar y cambian al actualizarse el día con la
aplicación abierta. No hay notificaciones externas ni actividad con el equipo apagado.

El superusuario tiene dashboard y Excel global, por entidad y mes. El Excel incluye
Clientes, Lotes, Contratos, Cuotas, Pagos y Entidades, con importes en centavos y
monedas explícitas. Los operadores tienen Mis transacciones y exportan sus propios
pagos. Los filtros de usuario, fecha y acción permiten revisar responsables.

El historial de auditoría es de solo lectura. No puede modificarse desde la
aplicación, ni siquiera como superusuario. El acceso administrativo al archivo
SQLite desde el disco está fuera de esta garantía.

La sesión vence tras 30 minutos sin actividad. Las consultas automáticas de día
no prolongan la sesión; las acciones del usuario sí. Use Cerrar sesión al terminar.
