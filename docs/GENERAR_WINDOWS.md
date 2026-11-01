# Generar y ejecutar el paquete Windows por tu cuenta

Código de referencia: 0.2.5. Revisado el 31 de octubre de 2026.
El resultado es un ZIP portátil con Python y dependencias; los equipos de destino
no necesitan instalar Python ni Node. La preparación inicial requiere internet.

## 1. Instalar las herramientas en la PC de preparación

- Windows de 64 bits.
- [Python 3.13.16](https://www.python.org/downloads/release/python-31316/):
  **Windows installer (64-bit)**, con el lanzador `py`.
- [Node.js](https://nodejs.org/en/download): rama 22 LTS de 64 bits como base
  compatible, o una LTS posterior que hayas comprobado.
- Git es opcional: también puedes descargar el código como ZIP desde GitHub.

Descarga además **Windows embeddable package (64-bit)** de la misma página de
Python. Es otro archivo: el instalador prepara tu PC y el ZIP embebible se incluirá
en el paquete portátil. Conserva ese ZIP sin descomprimir.

3.13.16 es la versión usada en el paquete actual para reproducirlo. La página
oficial puede ofrecer revisiones posteriores; un cambio de runtime debe validarse.

## 2. Descargar el código correcto

En [GitHub, codex/v0.2.5](https://github.com/DavidECerros/GrupoAbogados_D_Honduras/tree/codex/v0.2.5),
pulsa Code > Download ZIP y extrae el contenido. Inicia sesión si el repositorio
es privado. Para el ejemplo, deja la raíz en `C:\GAH\fuente-v0.2.5`.
Dentro deben verse `backend`, `frontend`, `scripts`, `requirements-lock.txt` e
`Iniciar.cmd`. Usa una carpeta nueva para cada entrega.

Si tienes Git, puedes descargarlo así:

```powershell
git clone --branch codex/v0.2.5 https://github.com/DavidECerros/GrupoAbogados_D_Honduras.git C:\GAH\fuente-v0.2.5
```

## 3. Abrir PowerShell y comprobar herramientas

No necesitas abrirlo como administrador. Ejecuta cada bloque por separado; si
aparece un error, resuélvelo antes de continuar.

```powershell
Set-Location -LiteralPath 'C:\GAH\fuente-v0.2.5'
py -3.13 --version
node --version
npm.cmd --version
py -3.13 -c "import struct; assert struct.calcsize('P') == 8, 'Se requiere Python de 64 bits'; print('Python de 64 bits correcto')"
```

Si no reconoce `py`, revisa el lanzador de Python. Si no reconoce Node/npm,
cierra y vuelve a abrir PowerShell después de instalar Node.

## 4. Preparar Python y compilar las pantallas

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

No es necesario activar el entorno: usamos su ejecutable directamente.

```powershell
Push-Location -LiteralPath 'frontend'
npm.cmd ci
npm.cmd run check
npm.cmd run build
Pop-Location
```

Debe existir `frontend\dist\index.html`. Repite la compilación cada vez que
modifiques las pantallas, aunque ya exista `dist`. `Instalar.ps1` omite ese paso
si encuentra una compilación previa; estos comandos la actualizan explícitamente.

En este punto puedes abrir `Iniciar.cmd` desde la raíz para ejecutar el código
en tu PC. Para construir el ZIP distribuible, continúa.

## 5. Descargar las dependencias para el paquete

Desde la raíz del código:

```powershell
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: --dest wheelhouse -r requirements-lock.txt
```

Debe terminar sin errores. `wheelhouse` guardará los paquetes compatibles con
Windows de 64 bits y Python 3.13. Ante «No matching distribution», comprueba
arquitectura, versión de Python y las dependencias fijadas. Conserva el error
para diagnosticarlo; no cambies versiones al azar.

## 6. Colocar y verificar el Python portátil

Crea `herramientas` dentro del código y coloca allí el ZIP descargado en el paso 1:

```text
C:\GAH\fuente-v0.2.5\herramientas\python-3.13.16-embed-amd64.zip
```

Verifica su huella oficial:

```powershell
$pythonPortableZip = Join-Path $PWD 'herramientas\python-3.13.16-embed-amd64.zip'
$expectedPythonSha = '97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'
if ((Get-FileHash -LiteralPath $pythonPortableZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedPythonSha) {
    throw 'El ZIP no coincide con Python 3.13.16 embebible de 64 bits.'
}
```

La huella corresponde únicamente a ese archivo. Fuente:
[archivos oficiales de Python](https://www.python.org/downloads/release/python-31316/).

## 7. Crear el paquete

```powershell
.\.venv\Scripts\python.exe scripts\build_windows.py --python-zip herramientas\python-3.13.16-embed-amd64.zip --wheels wheelhouse
```

El script genera:

```text
release\GrupoAbogados_D_Honduras-Windows\
release\GrupoAbogados_D_Honduras-Windows-v0.2.5.zip
```

Incluye runtime, dependencias, código, pantallas compiladas, documentación,
lanzadores y `manifest.json` con las huellas de los archivos. No incorpora la
base de trabajo, recibos ni credenciales de tu instalación.

Si dice «El paquete ya existe», usa una copia nueva del código para construir.
También puedes archivar manualmente la carpeta de paquete anterior conservando
su ZIP y repetir. El script protege la carpeta existente; no mezcles versiones.

## 8. Probar con datos ficticios

Extrae el ZIP en una carpeta de prueba y comprueba el runtime:

```powershell
Set-Location -LiteralPath 'C:\GAH\prueba\GrupoAbogados_D_Honduras-Windows'
.\runtime\python.exe -c "from backend.app import app; print(app.version)"
```

Debe mostrar `0.2.5`. Para una instalación ficticia independiente:

```powershell
$env:GESTOR_DATA_DIR = Join-Path $env:TEMP 'GAH-prueba-v0.2.5'
.\runtime\python.exe scripts\run.py --port 8025
```

Abre `http://127.0.0.1:8025` si el navegador no se abre. Esta prueba guarda sus
datos en la carpeta temporal indicada. Crea un usuario y registros ficticios;
prueba guardar, editar, un cobro, recibo y exportación. Termina con Ctrl+C.
Después quita la variable de esa sesión:

```powershell
Remove-Item Env:GESTOR_DATA_DIR
```

No restaures datos reales en la carpeta temporal para esta comprobación inicial.

## 9. Entregar y usar

1. Copia el ZIP completo a la PC de destino y extrae todos los archivos.
2. Abre `Iniciar.cmd`: ejecuta el servidor en segundo plano y abre el navegador.
3. Usa `Detener.cmd` para detenerlo. Cerrar el navegador no detiene el servidor.
4. Para diagnosticar errores, detén el servidor y abre `IniciarConsola.cmd`.

El resultado es portátil; no genera un instalador MSI ni un único EXE. Conserva
toda la carpeta, incluyendo `runtime`, `backend`, `scripts` y `frontend\dist`.

## 10. Actualizar sin perder datos

Haz y descarga un respaldo desde el sistema. Ejecuta `Detener.cmd` de la versión
anterior. Extrae la nueva en otra carpeta y abre su `Iniciar.cmd` con el mismo
usuario de Windows y la misma ubicación de datos.

La ubicación predeterminada es `%LOCALAPPDATA%\GrupoAbogados_D_Honduras`. Si
elegiste otra desde el sistema o con `GESTOR_DATA_DIR`, conserva esa ubicación.
Para cambiar de PC, usa respaldo/restauración; el ZIP del programa no lleva datos.
Si el puerto 8000 está ocupado, detén la instalación anterior. Si ves pantallas
viejas, revisa la versión y pulsa Ctrl+F5.

## Versiones futuras

Descarga la rama correspondiente y sigue su documentación. Si tú creas una
entrega nueva, mantén coherente la versión en `backend/app.py`,
`frontend/package.json`, las dos entradas del proyecto en
`frontend/package-lock.json`, el pie de `frontend/src/main.jsx` y la versión/nombre
del ZIP en `scripts/build_windows.py`. Actualiza el registro de cambios.
Modifica solo la versión del proyecto; un reemplazo global puede alterar
las versiones de las dependencias.
