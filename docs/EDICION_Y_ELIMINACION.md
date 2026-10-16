# Edición, eliminación y tarifas — v0.2.3

## Tarifas independientes por lotificadora

Como superusuario, abra Configuración → Configurar tarifas y seleccione el nombre
de la lotificadora. También puede usar Lotificadoras → Tarifas m² / vara².
Registre precio por m², precio por vara² y moneda. Guardar una lotificadora no
cambia la tarifa de ninguna otra. Los administradores y usuarios estándar pueden
consultar la tarifa de sus entidades, pero no modificarla.

Al actualizar, la tarifa global anterior se copia una vez a las lotificadoras
existentes para conservar el comportamiento. Después son independientes.
Una lotificadora nueva comienza sin tarifas por superficie. El tipo de cambio
HNL por USD y el factor m²/vara² permanecen a nivel de instalación.

## Precio fijo, superficie y prima

En Lotes → Editar, seleccione primero Cómo se determina el precio del lote:

- Precio total fijo: se utiliza el valor ingresado, por ejemplo HNL 250,000.
- Por m²: área del lote × tarifa de su lotificadora por m².
- Por vara²: área del lote en varas² × tarifa de su lotificadora por vara².

En modo por superficie, el valor manual guardado no se utiliza; no se muestra
como un campo editable para evitar confusión. Si quiere vender en HNL 250,000,
seleccione Precio total fijo e ingrese 250000. Para 155 m² a 1548.39 por m²,
el precio calculado es 240000.45, antes de restar prima.

Nueva venta muestra el desglose explícito. Con precio fijo 250000 y prima
acordada 10000, las cuotas financian 240000. La prima se resta una sola vez.
Escribir la prima acordada no registra dinero recibido: su obligación permanece
pendiente hasta que registre el cobro. Los contratos anteriores conservan las
condiciones de venta; cambiar tarifas o editar el lote no los recalcula.

## Acciones disponibles para el superusuario

| Módulo | Modificar | Eliminar / anular | Recuperar |
|---|---|---|---|
| Clientes | Datos e identidad según permisos | Eliminación recuperable; conserva contratos y cobros | Mostrar registros → Eliminados / anulados → Restaurar |
| Lotes | Código, ubicación, área, modo y precio fijo | Eliminación recuperable; conserva historial | Restaurar; mantiene su disponibilidad real |
| Reservas | Cliente, lote y vencimiento mientras esté activa | Libera el lote si estaba activa y archiva la reserva | Restaurar el registro histórico; una reserva liberada no vuelve a bloquear el lote |
| Contratos | Estado de cuenta → Modificar condiciones | Anular; requiere no tener cobros vigentes | Reactivar si el lote sigue disponible y el cliente está activo |
| Cobros y recibos | Fecha, método, referencia y notas con motivo | Anular; conserva folio y revierte las aplicaciones al saldo | Registrar el cobro correcto; no se reutiliza un cobro anulado |
| Planos | Coordenadas, rumbos y demás datos editables; propietario consultado del lote y título fijo | Eliminación recuperable | Restaurar |
| Usuarios | Nombre, rol, permisos, lotificadoras y estado | Desactivar y cerrar sesiones | Reactivar; el superusuario está protegido |
| Lotificadoras | Nombre, moneda, estado y tarifas propias | Archivar | Restaurar o cambiar a activa |
| Autorizaciones | Motivo mientras esté pendiente | Retirar la solicitud pendiente; queda rechazada con motivo | Crear otra solicitud cuando corresponda |

Resumen, Morosidad e Historial muestran datos derivados o auditoría. Para corregir
una cifra se modifica su registro de origen; no se borra la auditoría.

Las bajas y restauraciones solicitan confirmación y motivo, crean un respaldo
previo y registran antes/después. El borrado recuperable oculta registros de
Vigentes; no destruye las relaciones en la base de datos. Los informes y estados
de cuenta conservan las referencias necesarias para trabajar con el historial.
Los filtros permiten consultar Vigentes, Eliminados / anulados o Todos.

Los importes y el contrato de un cobro ya registrado se corrigen anulándolo y
registrando el correcto. Modificar sus datos descriptivos conserva importe,
saldo y folio; el PDF se regenera con los datos corregidos. Anular un cobro no
realiza una devolución bancaria ni elimina su evidencia.

## Depuración, precio fijo y reportes

En Eliminados / anulados, el superusuario puede Eliminar definitivamente lotes
y clientes sin referencias para liberar códigos y documentos. Se genera respaldo
y auditoría; los registros con historial deben restaurarse y corregirse.
El precio fijo solo lo modifica el superusuario, también validado en la API.
Consulte [reportería y estados](REPORTERIA_Y_ESTADOS.md) para exportaciones,
plan de pagos y escrituración.

## Pruebas y actualización

La versión incluye 101 pruebas, con edición repetida de lotes, clientes, reservas,
contratos, cobros y planos; tarifas distintas por entidad; restauración de
respaldos y verificaciones de permisos y saldos.

Cree respaldo, detenga la versión anterior y use el paquete Windows v0.2.3 en
una carpeta nueva. Ejecute su Iniciar.cmd y recargue con Ctrl+F5. Se conservan
los datos externos y se migra al esquema 6. No use el acceso directo anterior
hasta que apunte a la carpeta nueva.
