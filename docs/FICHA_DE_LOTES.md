# Ficha de escritura del lote

En Lotes, abra Nuevo lote o Editar lote. El formulario principal solicita:

- Código para identificar el lote dentro de su lotificadora.
- Nombre del cliente tal como aparece en la escritura, documento y contacto.
- Dirección literal del terreno, con espacio para varias líneas.
- Cada lado: identificación (Norte, Sur, 1–2, etc.), medida en metros,
  rumbo opcional y colindancia. Puede agregar o quitar lados.

Puede seleccionar un cliente registrado de la misma lotificadora para copiar sus
datos. La ficha conserva su propia redacción de escritura: editarla no cambia
el catálogo de clientes ni el titular de un contrato. La captura manual se guarda
en la ficha; para usar ese cliente en contratos, regístrelo en Clientes y vincúlelo.

Los datos de venta y superficie están plegados en una sección opcional. Puede
guardar un lote sin precio; aparecerá como Pendiente de precio. El superusuario
debe configurar el precio fijo o la tarifa por superficie antes de venderlo.
Al editar un lote anterior se conservan sus valores, aunque la sección esté cerrada.

En el listado, la columna Colindancias permite desplegar los lados para consultar
medidas, rumbos y vecinos. La búsqueda incluye cliente, documento y dirección.
Excel y Reportería incluyen la ficha. En las plantillas, las colindancias usan
una lista JSON (ejemplo en la hoja Instrucciones); las plantillas anteriores
continúan funcionando y conservan los datos de escritura al actualizar registros.

La versión 0.2.5 migra al esquema 7 y conserva contratos, cobros y recibos.
Haga respaldo y detenga la versión anterior antes de reemplazar el programa.
