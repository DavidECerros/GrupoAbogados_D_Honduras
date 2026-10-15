# Áreas, tarifas, usuarios y planos — v0.2.0

## Preparar las tarifas

Entre como superusuario a Configuración. Junto a la tasa HNL por USD encontrará
precio por m², precio por vara², moneda de las tarifas y factor de conversión.
Ambas tarifas son independientes: no se deduce una de la otra.
El factor inicial es 0.697224 m² por vara², configurable según el levantamiento.
Guardar tarifas requiere superusuario, incluso si otro usuario es administrador.

En Lotes registre el área en m² o vara². El sistema conserva el área canónica en
m² con seis decimales y muestra su equivalencia. Seleccione por lote cómo vender:
precio fijo, área por tarifa de m² o área por tarifa de vara².
Los lotes anteriores conservan su precio fijo hasta que se editen expresamente.
La tarifa por superficie utiliza la moneda definida en Configuración.

En Nueva venta seleccione el lote: el servidor calcula el precio. Para los lotes
por superficie ese precio es de solo lectura. Se redondea al centavo después de
multiplicar; no se redondea previamente el área de cálculo en varas.
Si la tarifa, conversión o área cambió desde que se seleccionó el lote, la venta
se rechaza y debe volver a seleccionarlo para revisar la cotización actual.
El contrato guarda área, unidad, tarifa, factor y moneda de la venta.
Cambiar tarifas o editar un lote no recalcula contratos existentes.

La plantilla Excel de lotes incluye Área m², Área vara² y Unidad de precio
(`fixed`, `m2`, `v2`). Complete una sola columna de área; si completa ambas deben
coincidir. Los archivos anteriores de seis columnas siguen admitidos y conservan
el área y unidad actuales al actualizar. Los estados de venta no se importan.

## Roles y módulos

Solo el superusuario administra usuarios, roles, lotificadoras, tarifas,
configuración, respaldos y SQL. El rol Administrador facilita la operación en sus
lotificadoras asignadas: lotes, clientes, reservas, ventas, cobros y planos.
El Usuario estándar parte de los accesos del operador anterior; el superusuario
puede personalizarlos. No se crean superusuarios adicionales.

En Usuarios seleccione el rol y las lotificadoras permitidas. Para cada módulo
puede elegir Desactivado, Solo consulta o Consulta y edición:

| ID | Clave | Módulo |
|---|---|---|
| M01 | dashboard | Resumen |
| M02 | clients | Clientes |
| M03 | lots | Lotes |
| M04 | reservations | Reservas |
| M05 | contracts | Contratos |
| M06 | payments | Cobros y recibos |
| M07 | arrears | Morosidad |
| M08 | transactions | Historial |
| M09 | approvals | Autorizaciones |
| M10 | plans | Planos y coordenadas |

Cambiar el rol en el formulario restablece sus accesos sugeridos antes de guardar.
Un módulo desactivado desaparece del menú y su API rechaza acceso directo.
Solo consulta impide modificaciones en el servidor. Los cambios se aplican en
la siguiente solicitud de una sesión abierta; vuelva a iniciar sesión para
actualizar su menú. Para registrar ventas o planos vinculados, habilite también
consulta a Clientes y Lotes para sus selectores. El acceso por módulo no elimina
las restricciones de lotificadora ni las autorizaciones especiales anteriores:
anulaciones, cesiones y cambios contractuales siguen requiriendo al superusuario.
Los administradores no reciben acceso global a cobros de otros operadores.

## Planos y coordenadas

Entre en Planos y coordenadas y cree un plano. El título es fijo y corresponde a
reunión de lotes. Seleccione el lote de referencia: se consulta su contrato
activo y se completa el cliente actual como propietario, sin edición libre.
Si no tiene contrato activo, seleccione un cliente registrado de esa lotificadora.
El servidor verifica y conserva la relación lote/cliente, incluso si se envía
un nombre distinto desde otra herramienta. Registre ubicación, fecha,
profesional y colegiación. Puede capturar:

- Vértices ordenados alrededor del perímetro. La colindancia corresponde al lado
  desde ese vértice al siguiente; el último regresa al primero.
- Rumbos y distancias de todos los lados hasta cerrar. Se admite azimut decimal
  de 0 a 360 grados o rumbo como `N75°07'08"W`. Ingrese el origen X/Y.

Sistemas: local en metros, GPS WGS84 (X longitud, Y latitud), UTM WGS84 zona
16 Norte (EPSG:32616) o 17 Norte (EPSG:32617). No ingrese NAD27 como WGS84.
En GPS se proyecta a la zona UTM correspondiente para medir en metros. Los
rumbos son de cuadrícula; no se presentan como norte magnético ni geodésico.
El Instituto de la Propiedad usa WGS84 y UTM en su
[formato de puntos geodésicos](https://www.ip.gob.hn/images/ip/docs/catastro/FORMATO_DE_solicitud_punto_geodesico_TGU_2021.pdf).
Confirme el sistema del levantamiento con su profesional.

Validar dibuja el polígono, calcula área, perímetro, distancias y rumbos. Se
rechazan cruces, vértices repetidos, áreas nulas y coordenadas geográficas fuera
del entorno de Honduras. Con rumbos se muestra el error de cierre: se admite
como máximo 5 cm o 1/1000 del perímetro, el mayor. Esa tolerancia es una validación
del programa, no una certificación de precisión topográfica. No se aplica un
ajuste de Bowditch ni se corrigen rumbos ingresados de forma silenciosa.

Reunir planos permite seleccionar de dos a diez planos de lotes distintos,
contiguos y con el mismo cliente propietario. El resultado calcula el contorno
exterior y conserva los códigos de los lotes. Se rechazan superposiciones,
separaciones, huecos y mezclas de coordenadas locales con georreferenciadas.
En coordenadas locales los planos deben usar el mismo origen y orientación.
La unión es geométrica: no fusiona contratos ni modifica los lotes registrados.
La unión usa [Shapely](https://shapely.readthedocs.io/en/stable/manual.html?highlight=distance).

Seleccione también el lado y nombre de calle o avenida para representarla junto
al terreno. El PDF muestra las colindancias alrededor del contorno cuando tiene
hasta seis lados, además del cuadro completo.

Guardar conserva el plano dentro de la base de datos; los respaldos lo incluyen.
Descargar PDF genera dibujo, norte, escala real, superficie, medidas y
colindancias, datos del profesional y espacio de firma. Si no cabe, se aumenta
el denominador de escala y se informa el utilizado. Imprima al 100%, sin ajustar.
Los lados extensos y coordenadas llevan hojas adicionales. El PDF descargado
corresponde a la última versión guardada. Crear o editar planos no modifica
automáticamente el área de un lote ni divide una finca registral.

Los planos son borradores técnicos para revisión y firma profesional. No se
generan firmas, sellos ni aprobaciones registrales. El programa no comprueba
titularidad ni límites oficiales y no reemplaza un levantamiento topográfico.

## Mapa opcional y GeoJSON

Activar mapa por internet carga las teselas públicas de OpenStreetMap con su
atribución visible. La cobertura y actualización dependen del proveedor; no es
un mapa satelital ni un catastro oficial. Se sigue su
[política de uso](https://operations.osmfoundation.org/policies/tiles/): sin
descarga masiva ni precarga offline. Solo esta vista necesita conexión; el
dibujo, validación y PDF funcionan sin internet.

Los planos GPS/UTM aparecen sobre el mapa; los locales no se georreferencian
automáticamente. En modo vértices GPS puede hacer clic para añadir puntos de
referencia. Para precisión use coordenadas medidas, no clics en el mapa.
La exportación GeoJSON permite reutilizar el polígono georreferenciado en SIG.
