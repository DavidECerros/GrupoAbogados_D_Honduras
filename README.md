# GrupoAbogados_D_Honduras

Gestor local de lotificadoras, ventas y cobros para Grupo Abogados D Honduras.
Implementación del documento de requisitos del 29 de septiembre de 2026.

## Estado del proyecto

Primera versión funcional, v0.1.0. Incluye interfaz en español y backend para
autenticación, segregación por entidad, clientes, lotes, reservas, contratos, cuotas,
cobros, cesiones, autorizaciones, auditoría, recibos PDF, exportación Excel y
respaldo/restauración. Las verificaciones y límites están en
[docs/ACEPTACION.md](docs/ACEPTACION.md). La aceptación en el equipo Windows 10
objetivo y las pruebas con usuarios del despacho están pendientes.

Tecnologías: Python/FastAPI, SQLite y React/Vite. Operación diaria local sin internet.
Importes en centavos, conversión con Decimal y sesión mediante cookie HttpOnly.

Los datos se guardan fuera del código, por defecto en
`%LOCALAPPDATA%\GrupoAbogados_D_Honduras`. Nunca se suben a GitHub.
No existen credenciales predeterminadas. El primer ingreso local presenta el
formulario para crear el único superusuario.

## Uso en Windows

El paquete `GrupoAbogados_D_Honduras-Windows-v0.1.0.zip` contiene Python,
dependencias y frontend compilado. Extraiga el ZIP en una carpeta local y abra
`Iniciar.cmd`. El navegador abrirá `http://localhost:8000`.
Use `CrearAccesoDirecto.ps1` para crear el acceso directo opcional.
No requiere Python, Node ni internet en el equipo de destino.
Pulse Ctrl+C en la ventana del servidor para cerrar de forma controlada.

Manuales: [instalación](docs/INSTALACION.md), [operación](docs/OPERACION.md),
[respaldo y recuperación](docs/RECUPERACION.md).

## Desarrollo del backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

La configuración inicial crea exactamente un superusuario desde el equipo local.
Los operadores deben cambiar su contraseña al primer ingreso. Las modificaciones
contractuales conservan la versión anterior y las aplicaciones de pagos. Se
reestructura solo el saldo pendiente, sin reducir precio o prima por debajo de
los importes ya pagados. Las cesiones se hacen efectivas el día del registro.

## Frontend y verificación

```powershell
cd frontend
npm ci
npm run check
npm run build
cd ..
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend tests scripts
.\.venv\Scripts\python.exe scripts\benchmark.py
```

`scripts/run.py` sirve la compilación React y la API desde el mismo origen.
No se ejecuta el servidor Vite en producción. Los endpoints API exigen sesión;
las mutaciones exigen además token CSRF. Las tareas de respaldo y restauración
detienen nuevas operaciones durante su ejecución, dentro de un solo proceso.

## Construcción del paquete

Descargue el ZIP embebible oficial de Python 3.13 de 64 bits desde python.org y
verifique su checksum publicado. Luego:

```powershell
.\.venv\Scripts\python.exe -m pip download -r requirements-lock.txt --only-binary=:all: --dest wheelhouse
.\.venv\Scripts\python.exe scripts\build_windows.py --python-zip RUTA_AL_ZIP --wheels wheelhouse
```

El constructor incluye únicamente código, interfaz y dependencias; excluye datos,
credenciales, recibos y respaldos. No sobrescribe un paquete anterior.

## Seguridad y publicación

Este repositorio contiene solo código, documentación y pruebas con datos sintéticos.
La base SQLite, recibos, logos, respaldos, secretos y entornos están excluidos de Git.
LAN requiere HTTPS y configuración explícita de hosts; el inicio local usa loopback.
Los recibos son comprobantes de cobro y no facturas fiscales.
