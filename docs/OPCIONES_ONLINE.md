# Opciones para compartir el sistema

Precios verificados el 8 de octubre de 2026, en dólares estadounidenses.
Estas opciones requieren configuración y validación antes de usar datos reales.

## Oficina, sin pago de alojamiento

Un equipo principal mantiene la aplicación y la base en su disco local. Las otras
computadoras acceden por navegador al mismo servidor usando la red de la oficina.
Todas consultan y modifican la misma base. El servidor debe estar encendido.
El modo LAN con HTTPS está descrito en INSTALACION.md.

## Servidor económico online

DigitalOcean publica un servidor Basic de 1 GiB RAM y 25 GiB SSD por US$6 al mes.
Sus copias semanales cuestan un 20% adicional del precio del servidor: el ejemplo
sería US$7.20 al mes con esa opción. Impuestos, dominio, exceso de consumo y otros
servicios se calculan aparte. También existen instancias menores, pero se propone
1 GiB como punto de partida que debe medirse con la carga real.

Fuente: https://www.digitalocean.com/pricing/droplets

La aplicación puede conservar SQLite en un disco persistente del servidor y
atender a los usuarios por HTTPS. Requiere preparar Linux, compilación, ejecución
como servicio, HTTPS, dominio o acceso privado y respaldos fuera del servidor.
El paquete Windows actual no es un despliegue online y todavía no se ha publicado
el sistema en ese proveedor. Se debe mantener una sola instancia de escritura.

## Opción gratuita para una prueba

Render ofrece web services gratuitos, pero se suspenden tras 15 minutos sin tráfico
y pierden archivos locales al reiniciar, suspenderse o desplegar. No permiten
disco persistente gratuito. La instalación SQLite actual no puede usarse allí
con datos que deban conservarse.

Fuente: https://render.com/docs/free

Una alternativa de prueba es adaptar el backend a PostgreSQL y mover los recibos
y logos a almacenamiento de objetos. Supabase Free incluye una base de hasta
500 MB y almacenamiento de archivos de hasta 1 GB. Sus proyectos gratuitos se
pausan tras un periodo de poca actividad. Esta combinación requiere migración,
pruebas y un mecanismo propio de respaldo; no es una sincronización automática
de la instalación local.

Fuentes: https://supabase.com/docs/guides/platform/billing-on-supabase
https://supabase.com/docs/guides/platform/free-project-pausing

Para operar diariamente con cobros, la propuesta es evaluar primero el servidor
económico con almacenamiento persistente. Para una demostración, puede evaluarse
la alternativa gratuita con sus límites y la adaptación indicada.
