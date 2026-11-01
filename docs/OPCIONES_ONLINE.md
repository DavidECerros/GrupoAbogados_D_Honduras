# Nube y acceso compartido: opciones para este sistema

Revisado el 31 de octubre de 2026. Precios en USD, antes de impuestos, dominio,
servicios adicionales e instalación. Esta revisión no contrata ni despliega servicios.

## Recomendación

Para operación diaria, empezar con DigitalOcean Basic de 1 GiB RAM y 25 GiB SSD:
US$6/mes. Con respaldo semanal del proveedor, que añade 20%, el ejemplo suma
US$7.20/mes. La capacidad debe validarse con usuarios, reportes y planos reales.
Además del respaldo del servidor, descargar respaldos de la aplicación fuera de él.
Fuente: [planes y respaldos de DigitalOcean](https://www.digitalocean.com/pricing/droplets).

El código actual usa SQLite y guarda recibos y logos en disco. Puede alojarse en
un solo servidor con almacenamiento persistente; no exige migrar primero a
PostgreSQL. Esta conclusión procede de revisar el código de la aplicación.

## Opciones

| Opción | Costo de alojamiento | Ventaja | Condición |
| --- | --- | --- | --- |
| DigitalOcean Basic 1 GiB | US$6/mes; ejemplo US$7.20 con respaldo semanal | Costo previsible y disco incluido | Administrar Linux y sus actualizaciones |
| Railway Hobby | Mínimo US$5/mes, incluye US$5 de consumo | Despliegue administrado | El total aumenta con consumo; confirmar plan apropiado para uso del despacho |
| Oracle Always Free | US$0 dentro de recursos y límites elegibles | Servidor sin mensualidad | Capacidad limitada y recuperación de instancias inactivas |
| PC de oficina + Cloudflare Tunnel/Access Free | Sin servidor alquilado; dominio, electricidad e internet aparte | Aprovecha el equipo existente | La PC sigue alojando el sistema y debe permanecer encendida |

Railway ofrece volúmenes persistentes. Free tiene US$1 de crédito mensual y
límites pequeños; no se puede prometer que cubra el sistema encendido todo el mes.
Hobby se presenta para proyectos personales; Pro para equipos y producción.
Revisar las condiciones para uso del despacho antes de contratar.
Fuentes: [precios](https://railway.com/pricing),
[planes](https://docs.railway.com/pricing/plans) y
[volúmenes](https://docs.railway.com/volumes).

Oracle permite recursos Always Free en la región principal. Puede faltar capacidad
y el proveedor puede recuperar instancias consideradas inactivas. Comprobar que
cómputo y almacenamiento seleccionados sean elegibles y que el estimado sea cero.
Fuente: [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

Cloudflare Tunnel conecta el servidor local mediante conexiones salientes. Se debe
configurar Access para usuarios autorizados, dominio estable y los parámetros HTTPS
del backend. El plan Free tiene límites vigentes y no aloja el programa.
Fuentes: [planes](https://www.cloudflare.com/plans/zero-trust-services/) y
[Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).

## Render gratuito

Render Free pierde los archivos locales al suspender, reiniciar o desplegar y no
ofrece disco persistente gratuito. Eso afecta a la SQLite, los recibos y los logos.
Su PostgreSQL gratuito expira tras 30 días. No utilizar esta configuración para
la cartera real; puede servir para demostraciones desechables.
Fuente: [límites oficiales](https://render.com/docs/free).

## Trabajo necesario para ponerlo online

1. Crear un servidor Linux y preparar dependencias de Linux y la interfaz compilada.
   El ZIP Windows corresponde a Windows; el servidor Linux se instala desde código.
2. Mantener una sola instancia del backend, con un proceso de escritura y una
   carpeta persistente, por ejemplo `/var/lib/grupoabogados`. Señalarla con
   `GESTOR_DATA_DIR`. Conservar toda la carpeta: base, recibos y logos.
3. Configurar dominio, HTTPS, inicio como servicio y respaldo fuera del servidor.
   Establecer `GESTOR_HTTPS=1` y `GESTOR_ALLOWED_HOSTS` con los nombres autorizados.
4. Si hay proxy o túnel, comprobar esquema HTTPS y host: la aplicación valida el
   origen de las operaciones. Confiar cabeceras solo desde el proxy previsto.
5. Completar el alta inicial del superusuario mediante acceso local controlado.
   El código restringe ese alta al equipo local; no quitar esa restricción para publicar.
6. Respaldar la instalación actual, detener sus operaciones y trasladar/restaurar
   los datos y archivos por un canal privado.
7. Probar primero con datos ficticios: permisos, dos equipos, cobros y recibos,
   reportes, planos, reinicio, actualización y restauración de un respaldo.
8. Después de validar, todos los operadores usarán una misma dirección web. Los
   cambios se verán al consultar o actualizar la pantalla desde otro equipo.

La aplicación no incluye sincronización bidireccional con copias locales ni
actualización instantánea de pantallas de otros usuarios. Subir el código a GitHub
no ejecuta el backend ni comparte por sí solo la base de datos.

SQLite debe permanecer en el disco local del servidor y atenderse a través de la
aplicación. OneDrive/Drive/Dropbox no sustituyen un servidor de base de datos.

## Oficina sin pago de alojamiento

Un equipo principal guarda los datos y los demás acceden por navegador en la red
local con HTTPS. El principal permanece encendido. Seguir
[Instalación: LAN](INSTALACION.md#lan-opcional-con-https).
Para acceder desde fuera de la oficina se necesita configurar acceso remoto.

Para generar el programa por cuenta propia: [instructivo Windows](GENERAR_WINDOWS.md).
