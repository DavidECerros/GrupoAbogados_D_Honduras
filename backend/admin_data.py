"""Local superuser tools. SQL cannot alter schema or bypass database constraints."""

import hashlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

from . import db as database
from .db import audit
from .finance import require

PREVIEWS = {}


def remember(user, payload):
    import secrets

    for key, value in list(PREVIEWS.items()):
        if value["expires"] < time.monotonic():
            PREVIEWS.pop(key, None)
    require(len(PREVIEWS) < 100, "Demasiadas vistas previas; espere unos minutos", 429)
    token = secrets.token_urlsafe(32)
    PREVIEWS[token] = {**payload, "user": user["id"], "expires": time.monotonic() + 600}
    return token


def recalled(user, token, purpose):
    value = PREVIEWS.get(token)
    require(
        value
        and value["user"] == user["id"]
        and value["expires"] > time.monotonic()
        and value["purpose"] == purpose,
        "Vista previa vencida. Vuelva a revisar el archivo o SQL",
        409,
    )
    return value


def table_info(db):
    return [
        {
            "name": r["name"],
            "rows": db.execute(
                'SELECT COUNT(*) FROM "' + r["name"].replace('"', '""') + '"'
            ).fetchone()[0],
            "columns": [
                dict(c)
                for c in db.execute('PRAGMA table_info("' + r["name"].replace('"', '""') + '")')
            ],
        }
        for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def state_hash(db, tables):
    digest = hashlib.sha256()
    for name in sorted(set(tables) - {"audit", "sessions", "sqlite_master"}):
        require(name.replace("_", "").isalnum(), "Tabla inválida")
        digest.update(name.encode())
        for row in db.execute(f'SELECT * FROM "{name}" ORDER BY rowid'):
            digest.update(json.dumps(tuple(row), default=str).encode())
    return digest.hexdigest()


def sql_operation(db, sql, dry_run=True):
    tables, writes = set(), set()

    def authorize(action, arg1, arg2, dbname, trigger):
        if dbname not in (None, "main"):
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ:
            if arg1:
                tables.add(arg1)
            return sqlite3.SQLITE_OK
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            if arg1 in (
                "audit",
                "sessions",
                "schema_version",
                "sqlite_master",
                "sqlite_sequence",
            ) or arg1.startswith("sqlite_"):
                return sqlite3.SQLITE_DENY
            tables.add(arg1)
            writes.add(arg1)
            return sqlite3.SQLITE_OK
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            return (
                sqlite3.SQLITE_DENY
                if (arg2 or "").lower() in ("load_extension", "readfile", "writefile")
                else sqlite3.SQLITE_OK
            )
        return sqlite3.SQLITE_DENY

    before = db.total_changes
    db.execute("SAVEPOINT sql_editor")
    deadline = time.monotonic() + 5
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    db.set_authorizer(authorize)
    try:
        cursor = db.execute(sql)
        columns = [c[0] for c in cursor.description] if cursor.description else []
        results = cursor.fetchmany(201) if columns else []
        result = {
            "columns": columns,
            "rows": [list(r) for r in results[:200]],
            "truncated": len(results) > 200,
            "changes": db.total_changes - before,
            "tables": sorted(tables),
            "writes": bool(writes),
        }
        cursor.close()
    except sqlite3.DatabaseError as exc:
        require(False, f"SQL rechazado: {exc}")
    finally:
        db.set_authorizer(None)
        db.set_progress_handler(None, 0)
        if dry_run:
            db.execute("ROLLBACK TO sql_editor")
        db.execute("RELEASE sql_editor")
    if not dry_run:
        require(
            not db.execute("PRAGMA foreign_key_check").fetchone(),
            "La modificación rompe relaciones",
        )
        require(
            db.execute("SELECT COUNT(*) FROM users WHERE role='superuser' AND active=1").fetchone()[
                0
            ]
            == 1,
            "Debe conservarse un superusuario activo",
        )
    return result


def relocate(db, user, target_text, reason):
    source = database.DATA
    target = Path(target_text).expanduser()
    require(
        not target_text.startswith("\\\\"),
        "La base activa debe estar en un disco local, no una ruta de red",
    )
    require(target.is_absolute(), "Use una ruta absoluta del equipo principal")
    target = target.resolve()
    require(
        target != source and source not in target.parents and target not in source.parents,
        "El destino debe estar fuera de la carpeta actual",
    )
    require(
        not target.exists() or (target.is_dir() and not any(target.iterdir())),
        "El destino debe ser una carpeta vacía",
    )
    require(
        not os.environ.get("GESTOR_DATA_DIR"),
        "Esta instalación usa GESTOR_DATA_DIR. Mueva los datos con el servidor detenido y actualice esa variable",
    )
    target.mkdir(parents=True, exist_ok=True)
    audit(
        db,
        user,
        "relocate_database",
        kind="database",
        reason=reason,
        before={"path": str(source)},
        after={"path": str(target)},
    )
    db.commit()
    replacement = sqlite3.connect(target / "gestor.sqlite3")
    try:
        db.backup(replacement)
        replacement.close()
        for folder in ("logos", "recibos", "backups"):
            if (source / folder).is_dir():
                shutil.copytree(source / folder, target / folder)
        config = database.LOCATION_CONFIG
        config.parent.mkdir(parents=True, exist_ok=True)
        pending = config.with_suffix(".tmp")
        pending.write_text(
            json.dumps({"data_dir": str(target)}, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(pending, config)
        database.MAINTENANCE = True
    except BaseException:
        replacement.close()
        audit(
            db,
            user,
            "relocate_database_failed",
            kind="database",
            reason="No se completó el traslado; se conserva la ubicación actual",
            result="failed",
        )
        # Preserve the original and the partial copy. Never erase user folders.
        raise
    return {"restart_required": True, "path": str(target), "original_retained": str(source)}
