# Instalación y arranque

## Paquete local de Windows

1. Copie el ZIP `GrupoAbogados_D_Honduras-Windows-v0.1.1.zip` al equipo principal.
2. Extraiga todos sus archivos a una carpeta local, por ejemplo `C:\GrupoAbogados`.
3. Abra `Iniciar.cmd`. Mantenga abierta la ventana del servidor durante el trabajo.
4. Entre a `http://localhost:8000`. En el primer inicio cree su superusuario con
   nombre, usuario y contraseña de al menos 12 caracteres. No hay contraseña inicial.
5. Cree una lotificadora y sus operadores. Asigne explícitamente las entidades.
6. Opcional: ejecute `CrearAccesoDirecto.ps1` del paquete para agregar el acceso directo.
7. Para cerrar, termine las operaciones en curso y pulse Ctrl+C en la ventana del servidor.

La operación diaria funciona sin internet. No utiliza CDN, fuentes remotas ni
proveedores externos de autenticación. El frontend está compilado y se sirve por
FastAPI desde el mismo origen. Python y las dependencias están incluidas.

## Almacenamiento

Por defecto los datos se guardan en `%LOCALAPPDATA%\GrupoAbogados_D_Honduras`.
La base de datos, los recibos y los logos no se guardan dentro del código.
`GESTOR_DATA_DIR` permite definir otra carpeta de datos local; debe conservarse
al actualizar y al recuperar el superusuario.
SQLite debe permanecer en el disco del equipo principal. No coloque la base en
una carpeta de red ni permita acceso directo desde equipos clientes.

Actualización: cierre el servidor, haga respaldo, conserve la carpeta de datos y
reemplace solo la carpeta del programa. La versión 0.1.1 migra automáticamente
el esquema 1 al 2 al iniciar: agrega el estado del cliente y conserva los registros.
También permite restaurar respaldos anteriores y migrarlos al esquema actual.

## Instalación desde código

Requiere Python 3.13 de 64 bits y Node 22 o posterior. Desde la raíz, ejecute
`Instalar.ps1`. El script crea el entorno, instala las dependencias y compila la
interfaz. La primera instalación desde código requiere internet si no se ha
preparado `wheelhouse` y la compilación. El paquete de ejecución evita ese requisito.

Las versiones exactas del backend se conservan en `requirements-lock.txt`; las
del frontend en `frontend/package-lock.json`.

El paquete construido en esta entrega incluye el runtime oficial
[Python 3.13.16 de 64 bits](https://www.python.org/downloads/release/python-31316/).
El ZIP embebible se verificó con el SHA-256 publicado por Python:
`97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297`.

## LAN opcional con HTTPS

El inicio normal escucha únicamente en loopback. Para LAN:

1. Termine la configuración inicial del superusuario desde el equipo principal.
2. Obtenga un certificado TLS emitido para el nombre DNS o IP del servidor. Para
   una red cerrada puede usar una autoridad interna y distribuir su certificado
   raíz a los equipos y teléfonos autorizados. No omita la validación TLS del navegador.
3. Guarde certificado y clave privada en el equipo principal, con acceso limitado
   al administrador del equipo. La clave no se incorpora al repositorio ni al paquete.
4. Inicie desde la carpeta del programa, por ejemplo:

   ```powershell
   .\runtime\python.exe scripts\run.py --lan --cert C:\Certificados\servidor.pem --key C:\Certificados\servidor.key --allowed-hosts localhost,127.0.0.1,gestor.local,192.168.1.50
   ```

5. Un administrador de Windows puede permitir el puerto solo en el perfil privado
   y restringido a la subred local:

   ```powershell
   New-NetFirewallRule -DisplayName 'Gestor lotificadoras HTTPS' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet
   ```

6. Los clientes abren `https://gestor.local:8000` con el equipo principal encendido.
   Verifique un certificado válido antes de ingresar credenciales. El lanzador
   rechaza LAN sin certificado, clave y lista explícita de hosts. No habilita HTTP en LAN.

Los ejemplos de DNS, IP y rutas deben adaptarse a la red real. La configuración
LAN y sus certificados aún deben verificarse en la red del despacho.
