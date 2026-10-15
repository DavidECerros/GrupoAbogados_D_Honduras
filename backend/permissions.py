"""Server enforced module access; the unique master keeps installation control."""

import json
import re

from .finance import require

MODULES = {
    "dashboard": "M01 · Resumen",
    "clients": "M02 · Clientes",
    "lots": "M03 · Lotes",
    "reservations": "M04 · Reservas",
    "contracts": "M05 · Contratos",
    "payments": "M06 · Cobros y recibos",
    "arrears": "M07 · Morosidad",
    "transactions": "M08 · Historial",
    "approvals": "M09 · Autorizaciones",
    "plans": "M10 · Planos y coordenadas",
}


def defaults(profile):
    if profile == "administrator":
        return {
            key: ("read" if key in ("dashboard", "arrears", "transactions") else "write")
            for key in MODULES
        }
    return {
        key: (
            "none"
            if key in ("dashboard", "plans")
            else "read"
            if key in ("lots", "arrears", "transactions")
            else "write"
        )
        for key in MODULES
    }


def resolved(user):
    if user["role"] == "superuser":
        return {key: "write" for key in MODULES}
    profile = user["profile"] if "profile" in user.keys() else "standard"
    raw = user["permissions"] if "permissions" in user.keys() else None
    return (
        json.loads(raw) if isinstance(raw, str) else raw if raw is not None else defaults(profile)
    )


def validate(permissions):
    require(
        permissions is None or set(permissions).issubset(MODULES),
        "Identificador de módulo inválido",
    )
    return (
        None
        if permissions is None
        else json.dumps({k: permissions.get(k, "none") for k in MODULES})
    )


def check(user, module, write=False):
    level = resolved(user).get(module, "none")
    require(
        level == "write" if write else level in ("read", "write"),
        f"Sin permiso {'de edición' if write else 'de consulta'} para {MODULES[module]}",
        403,
    )


def guard(user, path, method):
    if user["role"] == "superuser":
        return
    if path in (
        "/api/auth/me",
        "/api/auth/password",
        "/api/auth/logout",
        "/api/entities",
        "/api/alerts",
        "/api/exchange-rate",
        "/api/land-prices",
        "/api/modules",
    ):
        return
    if path.startswith("/api/auth/"):
        return
    master = ("/api/admin/", "/api/users", "/api/settings", "/api/backups")
    if path.startswith(master) or (
        path.startswith("/api/entities/") and not re.search(r"/entities/\d+/", path)
    ):
        require(False, "Esta función es exclusiva del superusuario", 403)
    module = next((key for key in MODULES if re.search(r"/" + key + r"(?:/|$|\.)", path)), None)
    if "/receipts/" in path or path == "/api/my-payments.xlsx":
        module = "payments"
    if path == "/api/export.xlsx":
        module = "transactions"
    if path == "/api/catalogs/import/execute":
        require(False, "La importación masiva requiere superusuario", 403)
    if module:
        check(
            user, module, method not in ("GET", "HEAD", "OPTIONS") and not path.endswith("/preview")
        )
