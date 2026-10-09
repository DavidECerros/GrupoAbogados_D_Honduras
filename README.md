# GrupoAbogados_D_Honduras

Gestor local de lotificadoras, ventas y cobros para Grupo Abogados D Honduras.
Implementación del documento de requisitos del 29 de septiembre de 2026.

## Estado del proyecto

En desarrollo. El backend implementa autenticación, segregación por entidad, clientes,
lotes, reservas, contratos, cuotas, cobros, cesiones, autorizaciones, auditoría,
recibos PDF, exportación Excel y respaldo/restauración. No debe usarse todavía con
datos reales: falta completar y verificar interfaz, instalación y aceptación.

Tecnologías: Python/FastAPI, SQLite y React/Vite. Operación diaria local sin internet.
Importes en centavos, conversión con Decimal y sesión mediante cookie HttpOnly.

Los datos se guardan fuera del código, por defecto en
`%LOCALAPPDATA%\GrupoAbogados_D_Honduras`. Nunca se suben a GitHub.
No existen credenciales predeterminadas.

## Desarrollo del backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

La configuración inicial crea exactamente un superusuario desde el equipo local.
Los operadores deben cambiar su contraseña al primer ingreso. Los cambios
financieros de contratos con historial de pagos están restringidos hasta definir
la reamortización, para conservar aplicaciones y recibos históricos.

## Seguridad y publicación

Este repositorio contiene solo código, documentación y pruebas con datos sintéticos.
La base SQLite, recibos, logos, respaldos, secretos y entornos están excluidos de Git.
LAN requiere HTTPS y configuración explícita de hosts; el inicio local usa loopback.
Los recibos son comprobantes de cobro y no facturas fiscales.
