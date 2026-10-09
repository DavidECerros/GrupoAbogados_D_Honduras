import hashlib
import io
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import admin_data, artifacts, catalog_io
from . import db as database
from . import models as m
from .db import audit, now, setting, today, transaction
from .finance import (
    admin,
    amend_contract,
    arrears,
    authorize,
    cents,
    create_payment,
    create_sale,
    payment_result,
    release_reservation,
    require,
    row,
    statement,
    transfer_contract,
    void_payment,
)

HASHER = PasswordHasher(time_cost=3, memory_cost=19456, parallelism=1)
DUMMY_HASH = HASHER.hash(secrets.token_hex(24))
SECURE = os.environ.get("GESTOR_HTTPS", "0") == "1"
ATTEMPTS = {}


@asynccontextmanager
async def lifespan(app):
    database.initialize()
    yield


app = FastAPI(
    title="Grupo Abogados D Honduras",
    version="0.1.2",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.environ.get("GESTOR_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(
        ","
    ),
)


@app.middleware("http")
async def guard(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host')}"
        if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Origen no autorizado"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(
        {"detail": "Datos duplicados o relacionados incompatibles"}, status_code=409
    )


@app.exception_handler(RequestValidationError)
async def request_invalid(request, exc):
    return JSONResponse(
        {
            "detail": "; ".join(
                f"{'.'.join(str(x) for x in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
        },
        status_code=422,
    )


@app.exception_handler(ValidationError)
async def action_invalid(request, exc):
    return JSONResponse(
        {"detail": "Los datos de la solicitud de autorización no son válidos"}, status_code=422
    )


@app.exception_handler(sqlite3.OperationalError)
async def database_error(request, exc):
    return JSONResponse(
        {
            "detail": "No fue posible escribir o leer los datos. La operación no se confirmó; reintente."
        },
        status_code=503,
    )


@app.exception_handler(Exception)
async def internal_error(request, exc):
    return JSONResponse(
        {
            "detail": "Error interno. Consulte al administrador; verifique el estado de la operación antes de reintentar."
        },
        status_code=500,
    )


def db_dependency(request: Request):
    database.REQUEST_GATE.acquire()
    db = None
    try:
        require(
            not database.MAINTENANCE,
            "Datos trasladados. Cierre el servidor y abra Iniciar.cmd nuevamente",
            503,
        )
        if (
            request.cookies.get("gestor_session")
            and request.headers.get("x-passive-request") != "1"
        ):
            probe = database.connect()
            try:
                token_hash = hashlib.sha256(request.cookies["gestor_session"].encode()).hexdigest()
                valid = probe.execute(
                    "SELECT s.last_seen FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND u.active=1",
                    (token_hash,),
                ).fetchone()
            finally:
                probe.close()
            if valid and datetime.fromisoformat(valid["last_seen"]) > datetime.now(
                timezone.utc
            ) - timedelta(minutes=30):
                artifacts.backup(daily=True)
        db = database.connect()
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        if db is not None:
            db.rollback()
        raise
    finally:
        if db is not None:
            db.close()
        database.REQUEST_GATE.release()


DB = Annotated[sqlite3.Connection, Depends(db_dependency, scope="function")]


def authenticated(request: Request, db: DB):
    token = request.cookies.get("gestor_session", "")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = db.execute(
        "SELECT s.*,u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND u.active=1",
        (token_hash,),
    ).fetchone()
    require(
        session
        and datetime.fromisoformat(session["last_seen"])
        > datetime.now(timezone.utc) - timedelta(minutes=30),
        "Sesión inválida o vencida",
        401,
    )
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        require(
            secrets.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]),
            "Verificación de sesión requerida",
            403,
        )
    user = {
        key: session[key]
        for key in (
            "id",
            "username",
            "full_name",
            "role",
            "active",
            "must_change",
            "created_at",
            "last_login",
        )
    }
    if user["must_change"]:
        require(
            request.url.path in ("/api/auth/me", "/api/auth/password", "/api/auth/logout"),
            "Debe cambiar su contraseña",
            403,
        )
    if request.method != "GET" or request.headers.get("x-passive-request") != "1":
        db.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now(), token_hash))
    return user


User = Annotated[dict, Depends(authenticated, scope="function")]


def public_user(db, user):
    result = {
        k: user[k]
        for k in (
            "id",
            "username",
            "full_name",
            "role",
            "active",
            "must_change",
            "created_at",
            "last_login",
        )
    }
    result["entity_ids"] = [
        r[0]
        for r in db.execute("SELECT entity_id FROM user_entities WHERE user_id=?", (user["id"],))
    ]
    return result


@app.get("/api/status")
def status(db: DB):
    return {
        "initialized": bool(db.execute("SELECT 1 FROM users WHERE role='superuser'").fetchone()),
        "version": "0.1.0",
    }


@app.post("/api/setup")
def setup(data: m.Setup, request: Request, db: DB):
    require(
        request.client.host in ("127.0.0.1", "::1", "testclient"),
        "Configuración inicial solo desde el equipo local",
        403,
    )
    require(not db.execute("SELECT 1 FROM users").fetchone(), "Instalación ya configurada", 409)
    require(len(data.password) >= 12, "La contraseña debe tener al menos 12 caracteres")
    identifier = db.execute(
        "INSERT INTO users(username,full_name,password_hash,role,created_at) VALUES(?,?,?,'superuser',?)",
        (data.username, data.full_name, HASHER.hash(data.password), now()),
    ).lastrowid
    audit(db, {"id": identifier, "role": "superuser"}, "setup", kind="user", record=identifier)
    return {"initialized": True}


@app.post("/api/auth/login")
def login(data: m.Login, request: Request, response: Response, db: DB):
    key = request.client.host
    recent = [
        v for v in ATTEMPTS.get(key, []) if v > datetime.now(timezone.utc) - timedelta(minutes=15)
    ]
    if len(recent) >= 60:
        return JSONResponse({"detail": "Demasiados intentos; espere 15 minutos"}, status_code=429)
    if len(ATTEMPTS) > 1000:
        ATTEMPTS.clear()
    ATTEMPTS[key] = recent
    user = db.execute(
        "SELECT * FROM users WHERE username=? COLLATE NOCASE", (data.username,)
    ).fetchone()
    valid = False
    try:
        valid = HASHER.verify(user["password_hash"] if user else DUMMY_HASH, data.password)
    except VerificationError:
        pass
    locked = (
        user
        and user["locked_until"]
        and datetime.fromisoformat(user["locked_until"]) > datetime.now(timezone.utc)
    )
    if not user or not valid or not user["active"] or locked:
        ATTEMPTS[key].append(datetime.now(timezone.utc))
        if user and not locked:
            failures = user["failures"] + 1
            until = (
                (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
                if failures >= 5
                else None
            )
            db.execute(
                "UPDATE users SET failures=?,locked_until=? WHERE id=?",
                (0 if until else failures, until, user["id"]),
            )
        audit(
            db,
            dict(user) if user else None,
            "login_failed",
            kind="user",
            record=user["id"] if user else None,
            result="denied",
        )
        return JSONResponse(
            {"detail": "Acceso inválido o temporalmente bloqueado"}, status_code=401
        )
    if HASHER.check_needs_rehash(user["password_hash"]):
        db.execute(
            "UPDATE users SET password_hash=? WHERE id=?", (HASHER.hash(data.password), user["id"])
        )
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions VALUES(?,?,?,?)",
        (hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, now()),
    )
    db.execute(
        "UPDATE users SET failures=0,locked_until=NULL,last_login=? WHERE id=?", (now(), user["id"])
    )
    audit(db, dict(user), "login", kind="user", record=user["id"])
    response.set_cookie(
        "gestor_session", token, httponly=True, secure=SECURE, samesite="strict", path="/"
    )
    return {
        "user": public_user(db, row(db, "users", user["id"])),
        "csrf": csrf,
        "today": str(today(db)),
    }


@app.get("/api/auth/me")
def me(request: Request, user: User, db: DB):
    token = hashlib.sha256(request.cookies["gestor_session"].encode()).hexdigest()
    return {
        "user": public_user(db, user),
        "csrf": db.execute("SELECT csrf FROM sessions WHERE token_hash=?", (token,)).fetchone()[0],
        "today": str(today(db)),
    }


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user: User, db: DB):
    db.execute(
        "DELETE FROM sessions WHERE token_hash=?",
        (hashlib.sha256(request.cookies["gestor_session"].encode()).hexdigest(),),
    )
    response.delete_cookie("gestor_session")
    audit(db, user, "logout")
    return {"ok": True}


@app.post("/api/auth/password")
def password(data: m.Password, request: Request, user: User, db: DB):
    try:
        HASHER.verify(row(db, "users", user["id"])["password_hash"], data.current_password)
    except VerificationError:
        raise HTTPException(422, "Contraseña actual incorrecta")
    db.execute(
        "UPDATE users SET password_hash=?,must_change=0 WHERE id=?",
        (HASHER.hash(data.new_password), user["id"]),
    )
    db.execute(
        "DELETE FROM sessions WHERE user_id=? AND token_hash<>?",
        (user["id"], hashlib.sha256(request.cookies["gestor_session"].encode()).hexdigest()),
    )
    audit(db, user, "change_password", kind="user", record=user["id"])
    return {"ok": True}


@app.get("/api/users")
def users(user: User, db: DB):
    admin(user)
    return [public_user(db, r) for r in db.execute("SELECT * FROM users ORDER BY id")]


@app.post("/api/users")
def create_user(data: m.Operator, user: User, db: DB):
    admin(user)
    identifier = db.execute(
        "INSERT INTO users(username,full_name,password_hash,role,must_change,created_at) VALUES(?,?,?,'operator',1,?)",
        (data.username, data.full_name, HASHER.hash(data.password), now()),
    ).lastrowid
    for entity in set(data.entity_ids):
        db.execute("INSERT INTO user_entities VALUES(?,?)", (identifier, entity))
    result = public_user(db, row(db, "users", identifier))
    audit(db, user, "create_user", kind="user", record=identifier, after=result)
    return result


@app.put("/api/users/{identifier}")
def update_user(identifier: int, data: m.UserUpdate, user: User, db: DB):
    admin(user)
    previous = public_user(db, row(db, "users", identifier))
    require(
        previous["role"] != "superuser" or data.active, "No se puede desactivar el superusuario"
    )
    db.execute(
        "UPDATE users SET full_name=?,active=? WHERE id=?",
        (data.full_name, int(data.active), identifier),
    )
    db.execute("DELETE FROM user_entities WHERE user_id=?", (identifier,))
    for entity in set(data.entity_ids):
        db.execute("INSERT INTO user_entities VALUES(?,?)", (identifier, entity))
    if not data.active:
        db.execute("DELETE FROM sessions WHERE user_id=?", (identifier,))
    result = public_user(db, row(db, "users", identifier))
    audit(db, user, "update_user", kind="user", record=identifier, before=previous, after=result)
    return result


@app.post("/api/users/{identifier}/reset-password")
def reset_password(identifier: int, data: m.Reset, user: User, db: DB):
    admin(user)
    row(db, "users", identifier)
    db.execute(
        "UPDATE users SET password_hash=?,must_change=1,failures=0,locked_until=NULL WHERE id=?",
        (HASHER.hash(data.password), identifier),
    )
    db.execute("DELETE FROM sessions WHERE user_id=?", (identifier,))
    audit(db, user, "reset_password", kind="user", record=identifier)
    return {"ok": True}


@app.get("/api/entities")
def entities(user: User, db: DB):
    if user["role"] == "superuser":
        return [dict(r) for r in db.execute("SELECT * FROM entities ORDER BY name")]
    return [
        dict(r)
        for r in db.execute(
            "SELECT e.* FROM entities e JOIN user_entities ue ON ue.entity_id=e.id WHERE ue.user_id=? ORDER BY e.name",
            (user["id"],),
        )
    ]


@app.post("/api/entities")
def create_entity(data: m.Entity, user: User, db: DB):
    admin(user)
    identifier = db.execute(
        "INSERT INTO entities(name,currency,status) VALUES(?,?,?)",
        (data.name, data.currency, data.status),
    ).lastrowid
    audit(db, user, "create_entity", None, "entity", identifier, after=data.model_dump())
    return row(db, "entities", identifier)


@app.put("/api/entities/{identifier}")
def update_entity(identifier: int, data: m.Entity, user: User, db: DB):
    admin(user)
    previous = row(db, "entities", identifier)
    db.execute(
        "UPDATE entities SET name=?,currency=?,status=? WHERE id=?",
        (data.name, data.currency, data.status, identifier),
    )
    audit(
        db,
        user,
        "update_entity",
        None,
        "entity",
        identifier,
        before=previous,
        after=data.model_dump(),
    )
    return row(db, "entities", identifier)


@app.delete("/api/entities/{identifier}")
def delete_entity(identifier: int, user: User, db: DB):
    admin(user)
    row(db, "entities", identifier)
    # Audit association itself preserves prior activity; only truly empty entities can disappear.
    for table in ("clients", "lots", "audit", "user_entities"):
        require(
            not db.execute(f"SELECT 1 FROM {table} WHERE entity_id=?", (identifier,)).fetchone(),
            "Entidad con historial: debe archivarse",
            409,
        )
    db.execute("DELETE FROM entities WHERE id=?", (identifier,))
    audit(db, user, "delete_entity", kind="entity", record=identifier)
    return {"ok": True}


@app.post("/api/entities/{identifier}/logo")
def logo(identifier: int, file: UploadFile, user: User, db: DB):
    admin(user)
    row(db, "entities", identifier)
    payload = file.file.read(2_000_001)
    require(len(payload) <= 2_000_000, "Logo máximo 2 MB")
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(payload))
        require(image.width * image.height <= 10_000_000, "Logo demasiado grande")
        image.thumbnail((600, 600))
        relative = f"logos/{identifier}-{hashlib.sha256(payload).hexdigest()[:16]}.png"
        (database.DATA / "logos").mkdir(exist_ok=True)
        image.convert("RGBA").save(database.DATA / relative, "PNG")
    except (OSError, Image.DecompressionBombError):
        raise HTTPException(422, "Imagen inválida")
    db.execute("UPDATE entities SET logo=? WHERE id=?", (relative, identifier))
    audit(db, user, "update_logo", None, "entity", identifier)
    return {"ok": True}


def pagination(page, size):
    require(page >= 1 and 1 <= size <= 100, "Paginación inválida")
    return size, (page - 1) * size


@app.get("/api/entities/{entity}/clients")
def clients(
    entity: int, user: User, db: DB, q: str = "", page: int = 1, size: int = 30, state: str = ""
):
    authorize(db, user, entity)
    limit, offset = pagination(page, size)
    filters = (entity, f"%{q}%", f"%{q}%")
    where = "entity_id=? AND (name LIKE ? OR document LIKE ?)"
    require(state in ("", "active", "inactive"), "Estado de cliente inválido")
    if state:
        where += " AND status=?"
        filters += (state,)
    return {
        "items": [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM clients WHERE {where} ORDER BY name LIMIT ? OFFSET ?",
                (*filters, limit, offset),
            )
        ],
        "total": db.execute(f"SELECT COUNT(*) FROM clients WHERE {where}", filters).fetchone()[0],
    }


@app.post("/api/entities/{entity}/clients")
def create_client(entity: int, data: m.Client, user: User, db: DB):
    authorize(db, user, entity, True)
    identifier = db.execute(
        "INSERT INTO clients(entity_id,name,document_type,document,phone,email,notes,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            entity,
            data.name,
            data.document_type,
            data.document,
            data.phone,
            data.email,
            data.notes,
            user["id"],
            now(),
        ),
    ).lastrowid
    result = row(db, "clients", identifier)
    audit(db, user, "create_client", entity, "client", identifier, after=result)
    return result


@app.put("/api/clients/{identifier}")
def edit_client(identifier: int, data: m.Client, user: User, db: DB):
    previous = row(db, "clients", identifier)
    authorize(db, user, previous["entity_id"], True)
    if user["role"] != "superuser":
        require(
            (data.name, data.document_type, data.document)
            == (previous["name"], previous["document_type"], previous["document"]),
            "Operador solo puede editar contacto y observaciones",
            403,
        )
    db.execute(
        "UPDATE clients SET name=?,document_type=?,document=?,phone=?,email=?,notes=? WHERE id=?",
        (
            data.name,
            data.document_type,
            data.document,
            data.phone,
            data.email,
            data.notes,
            identifier,
        ),
    )
    result = row(db, "clients", identifier)
    audit(
        db,
        user,
        "update_client",
        previous["entity_id"],
        "client",
        identifier,
        before=previous,
        after=result,
    )
    return result


@app.patch("/api/clients/{identifier}/status")
def change_client_status(identifier: int, data: m.ClientStatus, user: User, db: DB):
    admin(user)
    previous = row(db, "clients", identifier)
    authorize(db, user, previous["entity_id"], True)
    if previous["status"] == data.status:
        return previous
    db.execute("UPDATE clients SET status=? WHERE id=?", (data.status, identifier))
    result = row(db, "clients", identifier)
    audit(
        db,
        user,
        "deactivate_client" if data.status == "inactive" else "reactivate_client",
        previous["entity_id"],
        "client",
        identifier,
        reason=data.reason,
        before=previous,
        after=result,
    )
    return result


@app.get("/api/entities/{entity}/lots")
def lots(
    entity: int, user: User, db: DB, q: str = "", state: str = "", page: int = 1, size: int = 30
):
    authorize(db, user, entity)
    limit, offset = pagination(page, size)
    where = "entity_id=? AND (code LIKE ? OR description LIKE ?) AND (?='' OR status=?)"
    filters = (entity, f"%{q}%", f"%{q}%", state, state)
    return {
        "items": [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM lots WHERE {where} ORDER BY code LIMIT ? OFFSET ?",
                (*filters, limit, offset),
            )
        ],
        "total": db.execute(f"SELECT COUNT(*) FROM lots WHERE {where}", filters).fetchone()[0],
    }


@app.post("/api/entities/{entity}/lots")
def create_lot(entity: int, data: m.Lot, user: User, db: DB):
    admin(user)
    authorize(db, user, entity, True)
    identifier = db.execute(
        "INSERT INTO lots(entity_id,code,description,price,currency) VALUES(?,?,?,?,?)",
        (entity, data.code, data.description, cents(data.price), data.currency),
    ).lastrowid
    result = row(db, "lots", identifier)
    audit(db, user, "create_lot", entity, "lot", identifier, after=result)
    return result


@app.put("/api/lots/{identifier}")
def edit_lot(identifier: int, data: m.Lot, user: User, db: DB):
    admin(user)
    previous = row(db, "lots", identifier)
    authorize(db, user, previous["entity_id"], True)
    db.execute(
        "UPDATE lots SET code=?,description=?,price=?,currency=? WHERE id=?",
        (data.code, data.description, cents(data.price), data.currency, identifier),
    )
    result = row(db, "lots", identifier)
    audit(
        db,
        user,
        "update_lot",
        previous["entity_id"],
        "lot",
        identifier,
        before=previous,
        after=result,
    )
    return result


@app.get("/api/entities/{entity}/reservations")
def reservations(entity: int, user: User, db: DB, page: int = 1, size: int = 30):
    authorize(db, user, entity)
    limit, offset = pagination(page, size)
    return {
        "items": [
            dict(r)
            for r in db.execute(
                "SELECT r.*,l.code lot,c.name client,CASE WHEN r.status='active' AND r.expires_on<? THEN 1 ELSE 0 END expired FROM reservations r JOIN lots l ON l.id=r.lot_id JOIN clients c ON c.id=r.client_id WHERE r.entity_id=? ORDER BY r.id DESC LIMIT ? OFFSET ?",
                (str(today(db)), entity, limit, offset),
            )
        ],
        "total": db.execute(
            "SELECT COUNT(*) FROM reservations WHERE entity_id=?", (entity,)
        ).fetchone()[0],
    }


@app.post("/api/entities/{entity}/reservations")
def reserve(entity: int, data: m.Reservation, user: User, db: DB):
    authorize(db, user, entity, True)
    lot, client = row(db, "lots", data.lot_id), row(db, "clients", data.client_id)
    require(
        lot["entity_id"] == entity and client["entity_id"] == entity,
        "Registros de otra entidad",
        403,
    )
    require(client["status"] == "active", "Cliente inhabilitado; reactívelo antes de reservar", 409)
    require(lot["status"] == "available", "Lote no disponible", 409)
    require(data.expires_on >= today(db), "La reserva ya venció")
    identifier = db.execute(
        "INSERT INTO reservations(entity_id,lot_id,client_id,expires_on,created_at,created_by) VALUES(?,?,?,?,?,?)",
        (entity, data.lot_id, data.client_id, str(data.expires_on), now(), user["id"]),
    ).lastrowid
    db.execute("UPDATE lots SET status='reserved' WHERE id=?", (data.lot_id,))
    audit(
        db,
        user,
        "create_reservation",
        entity,
        "reservation",
        identifier,
        after=data.model_dump(mode="json"),
    )
    return row(db, "reservations", identifier)


@app.post("/api/reservations/{identifier}/release")
def release(identifier: int, data: m.Reason, user: User, db: DB):
    release_reservation(db, user, identifier, data.reason)
    return {"ok": True}


@app.get("/api/entities/{entity}/contracts")
def contracts(entity: int, user: User, db: DB, q: str = "", page: int = 1, size: int = 30):
    authorize(db, user, entity)
    limit, offset = pagination(page, size)
    base = "FROM contracts c JOIN clients cl ON cl.id=c.client_id JOIN lots l ON l.id=c.lot_id WHERE c.entity_id=? AND (cl.name LIKE ? OR cl.document LIKE ? OR l.code LIKE ?)"
    filters = (entity, f"%{q}%", f"%{q}%", f"%{q}%")
    return {
        "items": [
            dict(r)
            for r in db.execute(
                "SELECT c.*,cl.name client,l.code lot,(SELECT SUM(amount-paid) FROM obligations WHERE contract_id=c.id) balance "
                + base
                + " ORDER BY c.id DESC LIMIT ? OFFSET ?",
                (*filters, limit, offset),
            )
        ],
        "total": db.execute("SELECT COUNT(*) " + base, filters).fetchone()[0],
    }


@app.post("/api/entities/{entity}/contracts")
def sale(entity: int, data: m.Sale, user: User, db: DB):
    return create_sale(db, user, entity, data)


@app.get("/api/contracts/{identifier}")
def account(identifier: int, user: User, db: DB):
    return statement(db, user, identifier)


@app.get("/api/contracts/{identifier}/versions")
def versions(identifier: int, user: User, db: DB):
    admin(user)
    authorize(db, user, row(db, "contracts", identifier)["entity_id"])
    return [
        dict(r)
        for r in db.execute(
            "SELECT * FROM contract_versions WHERE contract_id=? ORDER BY version", (identifier,)
        )
    ]


@app.post("/api/contracts/{identifier}/transfer")
def transfer(identifier: int, data: m.Transfer, user: User, db: DB):
    transfer_contract(db, user, identifier, data)
    return statement(db, user, identifier)


@app.put("/api/contracts/{identifier}")
def amend(identifier: int, data: m.Amendment, user: User, db: DB):
    amend_contract(db, user, identifier, data)
    return statement(db, user, identifier)


@app.post("/api/payments")
def pay(data: m.Payment, user: User, db: DB):
    # Commit the financial transaction before attempting PDF output.
    result = create_payment(db, user, data)
    db.commit()
    try:
        db.execute("BEGIN IMMEDIATE")
        artifacts.generate_receipt(db, result["receipt_id"])
        db.commit()
        result = payment_result(db, result["id"])
    except Exception:
        db.rollback()
        result["receipt_warning"] = "Pago confirmado. PDF pendiente; regenere el mismo recibo."
    return result


@app.post("/api/payments/{identifier}/void")
def void(identifier: int, data: m.Reason, user: User, db: DB):
    void_payment(db, user, identifier, data.reason)
    return finish_void_receipt(db, identifier)


def finish_void_receipt(db, payment_id):
    receipt_id = db.execute("SELECT id FROM receipts WHERE payment_id=?", (payment_id,)).fetchone()[
        0
    ]
    db.commit()
    try:
        db.execute("BEGIN IMMEDIATE")
        artifacts.generate_receipt(db, receipt_id)
        db.commit()
        return {"ok": True}
    except Exception:
        db.rollback()
        return {
            "ok": True,
            "receipt_warning": "Anulación confirmada. Regenere el PDF anulado desde la descarga del recibo.",
        }


def receipt_permission(db, user, identifier):
    receipt = row(db, "receipts", identifier)
    authorize(db, user, receipt["entity_id"])
    payment = row(db, "payments", receipt["payment_id"])
    require(
        user["role"] == "superuser" or payment["created_by"] == user["id"],
        "Solo puede reimprimir sus propios recibos",
        403,
    )
    return receipt


@app.get("/api/receipts/{identifier}/pdf")
def pdf(identifier: int, user: User, db: DB):
    receipt = receipt_permission(db, user, identifier)
    path = artifacts.generate_receipt(db, identifier)
    audit(db, user, "download_receipt", receipt["entity_id"], "receipt", identifier)
    return Response(
        path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{receipt["folio"]}.pdf"'},
    )


@app.post("/api/receipts/{identifier}/regenerate")
def regenerate(identifier: int, user: User, db: DB):
    receipt = receipt_permission(db, user, identifier)
    artifacts.generate_receipt(db, identifier)
    audit(db, user, "regenerate_receipt", receipt["entity_id"], "receipt", identifier)
    return {"ok": True}


@app.get("/api/entities/{entity}/payments")
def payments(
    entity: int,
    user: User,
    db: DB,
    since: date | None = None,
    until: date | None = None,
    state: str = "",
    page: int = 1,
    size: int = 30,
):
    authorize(db, user, entity)
    limit, offset = pagination(page, size)
    where = "entity_id=?"
    args = [entity]
    for field, value, operator in [
        ("payment_date", str(since) if since else None, ">="),
        ("payment_date", str(until) if until else None, "<="),
        ("status", state, "="),
    ]:
        if value:
            where += f" AND {field}{operator}?"
            args.append(value)
    if user["role"] != "superuser":
        where += " AND created_by=?"
        args.append(user["id"])
    selected = "SELECT * FROM payments WHERE " + where + " ORDER BY id DESC LIMIT ? OFFSET ?"
    sql = (
        "SELECT p.*,cl.name client,l.code lot,u.full_name operator,r.id receipt_id,r.folio,r.status receipt_status FROM ("
        + selected
        + ") p JOIN clients cl ON cl.id=p.client_id JOIN contracts c ON c.id=p.contract_id JOIN lots l ON l.id=c.lot_id JOIN receipts r ON r.payment_id=p.id JOIN users u ON u.id=p.created_by ORDER BY p.id DESC"
    )
    return {
        "items": [dict(r) for r in db.execute(sql, (*args, limit, offset))],
        "total": db.execute("SELECT COUNT(*) FROM payments WHERE " + where, args).fetchone()[0],
    }


@app.get("/api/entities/{entity}/arrears")
def mora(
    entity: int,
    user: User,
    db: DB,
    client_id: int | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    page: int = 1,
    size: int = 30,
    q: str = "",
):
    authorize(db, user, entity)
    limit, offset = pagination(page, size)
    records = arrears(db, entity, client_id, due_from, due_to, q)
    totals = {
        currency: sum(r["overdue"] for r in records if r["currency"] == currency)
        for currency in ("HNL", "USD")
    }
    return {
        "items": records[offset : offset + limit],
        "total": len(records),
        "overdue_totals": totals,
        "today": str(today(db)),
    }


@app.get("/api/dashboard")
def dashboard(user: User, db: DB, entity: int | None = None, month: str = ""):
    admin(user)
    if entity:
        authorize(db, user, entity)
    month = month or today(db).strftime("%Y-%m")
    try:
        start = date.fromisoformat(month + "-01")
    except ValueError:
        raise HTTPException(422, "Mes inválido")
    where = " AND entity_id=?" if entity else ""
    args = [entity] if entity else []
    lots = {
        r["status"]: r["count"]
        for r in db.execute(
            "SELECT status,COUNT(*) count FROM lots WHERE 1=1" + where + " GROUP BY status", args
        )
    }
    months = []
    for delta in range(5, -1, -1):
        index = start.year * 12 + start.month - 1 - delta
        year, zero_month = divmod(index, 12)
        key = f"{year:04}-{zero_month + 1:02}"
        months.append(key)
    aggregates = [
        dict(r)
        for r in db.execute(
            "SELECT substr(payment_date,1,7) month,received_currency currency,SUM(received) amount FROM payments WHERE status='valid' AND payment_date>=? AND payment_date<=?"
            + where
            + " GROUP BY substr(payment_date,1,7),received_currency",
            [months[0] + "-01", month + "-31", *args],
        )
    ]
    totals = [
        {"currency": r["currency"], "amount": r["amount"]}
        for r in aggregates
        if r["month"] == month
    ]
    chart = [
        {
            "month": key,
            **{
                currency: sum(
                    r["amount"]
                    for r in aggregates
                    if r["month"] == key and r["currency"] == currency
                )
                for currency in ("HNL", "USD")
            },
        }
        for key in months
    ]
    top = {}
    for currency in ("HNL", "USD"):
        sql = "SELECT e.name entity,cl.name client,c.currency,SUM(o.amount-o.paid) overdue FROM contracts c JOIN obligations o ON o.contract_id=c.id JOIN clients cl ON cl.id=c.client_id JOIN entities e ON e.id=c.entity_id WHERE c.status='active' AND c.currency=? AND o.due_date<? AND o.amount>o.paid"
        params = [currency, str(today(db))]
        if entity:
            sql += " AND c.entity_id=?"
            params.append(entity)
        sql += " GROUP BY c.entity_id,c.client_id,c.currency ORDER BY overdue DESC LIMIT 5"
        top[currency] = [dict(r) for r in db.execute(sql, params)]
    return {
        "lots": lots,
        "collection": totals,
        "chart": chart,
        "top_debtors": top,
        "today": str(today(db)),
    }


@app.post("/api/entities/{entity}/approvals")
def request_approval(entity: int, data: m.Approval, user: User, db: DB):
    authorize(db, user, entity, True)
    require("reason" not in data.payload, "El motivo debe enviarse por separado")
    table = {
        "void_payment": "payments",
        "release_reservation": "reservations",
        "transfer_contract": "contracts",
        "amend_contract": "contracts",
    }[data.action]
    record = row(db, table, data.record_id)
    require(record["entity_id"] == entity, "Registro de otra entidad", 403)
    if data.action == "void_payment" and user["role"] != "superuser":
        require(
            record["created_by"] == user["id"], "Solo puede solicitar anulación de sus pagos", 403
        )
    if data.action == "transfer_contract":
        parsed = m.Transfer(reason=data.reason, **data.payload)
        require(
            row(db, "clients", parsed.new_client_id)["status"] == "active",
            "Cliente inhabilitado; reactívelo antes de ceder",
            409,
        )
        require(
            row(db, "clients", parsed.new_client_id)["entity_id"] == entity,
            "Cliente de otra entidad",
            403,
        )
    if data.action == "amend_contract":
        m.Amendment(reason=data.reason, **data.payload)
    identifier = db.execute(
        "INSERT INTO approvals(entity_id,action,record_id,payload,reason,requested_by,created_at) VALUES(?,?,?,?,?,?,?)",
        (
            entity,
            data.action,
            data.record_id,
            json.dumps(data.payload),
            data.reason,
            user["id"],
            now(),
        ),
    ).lastrowid
    audit(
        db,
        user,
        "request_approval",
        entity,
        "approval",
        identifier,
        reason=data.reason,
        after=data.model_dump(),
    )
    return row(db, "approvals", identifier)


@app.get("/api/approvals")
def approvals(user: User, db: DB, entity: int | None = None, page: int = 1, size: int = 30):
    limit, offset = pagination(page, size)
    sql = "SELECT a.*,u.full_name requester FROM approvals a JOIN users u ON u.id=a.requested_by WHERE 1=1"
    args = []
    if entity:
        authorize(db, user, entity)
        sql += " AND a.entity_id=?"
        args.append(entity)
    if user["role"] != "superuser":
        sql += " AND a.requested_by=? AND a.entity_id IN (SELECT entity_id FROM user_entities WHERE user_id=?)"
        args.extend([user["id"], user["id"]])
    total = db.execute("SELECT COUNT(*) FROM (" + sql + ")", args).fetchone()[0]
    return {
        "items": [
            dict(r)
            for r in db.execute(
                sql + " ORDER BY a.id DESC LIMIT ? OFFSET ?", (*args, limit, offset)
            )
        ],
        "total": total,
    }


@app.post("/api/approvals/{identifier}/resolve")
def resolve(identifier: int, data: m.Decision, user: User, db: DB):
    admin(user)
    approval = row(db, "approvals", identifier)
    require(approval["status"] == "pending", "Solicitud ya resuelta", 409)
    if data.approve:
        payload = json.loads(approval["payload"])
        action, record = approval["action"], approval["record_id"]
        if action == "void_payment":
            void_payment(db, user, record, approval["reason"])
        elif action == "release_reservation":
            release_reservation(db, user, record, approval["reason"])
        elif action == "transfer_contract":
            transfer_contract(db, user, record, m.Transfer(reason=approval["reason"], **payload))
        else:
            amend_contract(db, user, record, m.Amendment(reason=approval["reason"], **payload))
    db.execute(
        "UPDATE approvals SET status=?,resolved_by=?,resolved_at=?,resolution=? WHERE id=?",
        ("approved" if data.approve else "rejected", user["id"], now(), data.reason, identifier),
    )
    audit(
        db,
        user,
        "resolve_approval",
        approval["entity_id"],
        "approval",
        identifier,
        data.reason,
        after={"approved": data.approve},
    )
    result = row(db, "approvals", identifier)
    if data.approve and approval["action"] == "void_payment":
        result.update(finish_void_receipt(db, approval["record_id"]))
    return result


def history_query(user, entity, user_id, since, until, action, state):
    where = " WHERE 1=1"
    args = []
    for field, value, operator in [
        ("a.entity_id", entity, "="),
        ("a.user_id", user_id if user["role"] == "superuser" else user["id"], "="),
        ("a.created_at", str(since) if since else None, ">="),
        ("a.created_at", str(until + timedelta(days=1)) if until else None, "<"),
        ("a.action", action, "="),
        ("a.result", state, "="),
    ]:
        if value:
            where += f" AND {field}{operator}?"
            args.append(value)
    if user["role"] != "superuser":
        where += " AND a.entity_id IN (SELECT entity_id FROM user_entities WHERE user_id=?)"
        args.append(user["id"])
    return where, args


@app.get("/api/transactions")
def transactions(
    user: User,
    db: DB,
    entity: int | None = None,
    user_id: int | None = None,
    since: date | None = None,
    until: date | None = None,
    action: str = "",
    state: str = "",
    page: int = 1,
    size: int = 30,
):
    if entity:
        authorize(db, user, entity)
    limit, offset = pagination(page, size)
    where, args = history_query(user, entity, user_id, since, until, action, state)
    base = (
        "FROM audit a LEFT JOIN users u ON u.id=a.user_id LEFT JOIN entities e ON e.id=a.entity_id"
    )
    items = [
        dict(r)
        for r in db.execute(
            "SELECT a.*,u.full_name operator,e.name entity "
            + base
            + where
            + " ORDER BY a.id DESC LIMIT ? OFFSET ?",
            (*args, limit, offset),
        )
    ]
    if user["role"] != "superuser":
        for item in items:
            item.pop("before_json", None)
            item.pop("after_json", None)
    # Payment totals obey the same entity assignment and user scope.
    totals_sql = "SELECT p.created_by,u.full_name operator,p.received_currency currency,SUM(p.received) amount FROM payments p JOIN users u ON u.id=p.created_by WHERE p.status='valid'"
    total_args = []
    for field, value, operator in [
        ("p.entity_id", entity, "="),
        ("p.created_by", user_id if user["role"] == "superuser" else user["id"], "="),
        ("p.payment_date", str(since) if since else None, ">="),
        ("p.payment_date", str(until) if until else None, "<="),
    ]:
        if value:
            totals_sql += f" AND {field}{operator}?"
            total_args.append(value)
    if user["role"] != "superuser":
        totals_sql += " AND p.entity_id IN (SELECT entity_id FROM user_entities WHERE user_id=?)"
        total_args.append(user["id"])
    return {
        "items": items,
        "total": db.execute("SELECT COUNT(*) " + base + where, args).fetchone()[0],
        "payment_totals": [
            dict(r)
            for r in db.execute(
                totals_sql + " GROUP BY p.created_by,p.received_currency", total_args
            )
        ],
    }


@app.get("/api/export.xlsx")
def export(user: User, db: DB, entity: int | None = None, month: str = ""):
    admin(user)
    if entity:
        authorize(db, user, entity)
    month = month or today(db).strftime("%Y-%m")
    try:
        date.fromisoformat(month + "-01")
    except ValueError:
        raise HTTPException(422, "Mes inválido")
    where = " WHERE entity_id=?" if entity else ""
    args = [entity] if entity else []
    tables = {
        name: [dict(r) for r in db.execute(f"SELECT * FROM {table}" + where, args)]
        for name, table in [("Clientes", "clients"), ("Lotes", "lots"), ("Contratos", "contracts")]
    }
    tables["Pagos"] = [
        dict(r)
        for r in db.execute(
            "SELECT p.*,r.folio,u.full_name operator FROM payments p JOIN receipts r ON r.payment_id=p.id JOIN users u ON u.id=p.created_by WHERE substr(p.payment_date,1,7)=?"
            + (" AND p.entity_id=?" if entity else ""),
            [month, *args],
        )
    ]
    tables["Cuotas"] = [
        dict(r)
        for r in db.execute(
            "SELECT o.*,c.entity_id,c.currency FROM obligations o JOIN contracts c ON c.id=o.contract_id"
            + (" WHERE c.entity_id=?" if entity else ""),
            args,
        )
    ]
    tables["Entidades"] = [
        dict(r)
        for r in db.execute(
            "SELECT id,name,currency,status FROM entities" + (" WHERE id=?" if entity else ""), args
        )
    ]
    audit(db, user, "export_global", entity, kind="export", after={"month": month})
    return Response(
        artifacts.export_excel(db, tables),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="reporte.xlsx"'},
    )


@app.get("/api/my-payments.xlsx")
def export_mine(
    user: User, db: DB, entity: int, since: date | None = None, until: date | None = None
):
    authorize(db, user, entity)
    sql = "SELECT p.id,p.entity_id,p.contract_id,p.payment_date,p.received,p.received_currency,p.applied,p.rate,p.method,p.bank_reference,p.status,p.balance_after,r.folio,cl.name client,l.code lot FROM payments p JOIN receipts r ON r.payment_id=p.id JOIN clients cl ON cl.id=p.client_id JOIN contracts c ON c.id=p.contract_id JOIN lots l ON l.id=c.lot_id WHERE p.created_by=? AND p.entity_id=?"
    args = [user["id"], entity]
    if since:
        sql += " AND p.payment_date>=?"
        args.append(str(since))
    if until:
        sql += " AND p.payment_date<=?"
        args.append(str(until))
    tables = {"Mis pagos": [dict(r) for r in db.execute(sql, args)]}
    audit(db, user, "export_own_payments", entity, kind="export")
    return Response(
        artifacts.export_excel(db, tables),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="mis-pagos.xlsx"'},
    )


@app.get("/api/settings")
def settings(user: User, db: DB):
    admin(user)
    return dict(db.execute("SELECT key,value FROM settings"))


@app.put("/api/settings")
def update_settings(data: m.Settings, user: User, db: DB):
    admin(user)
    try:
        ZoneInfo(data.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Zona horaria inválida")
    if data.backup_destination:
        destination = Path(data.backup_destination)
        require(destination.is_absolute(), "Destino de respaldo debe ser absoluto")
        require(
            destination.resolve() != database.DATA
            and database.DATA not in destination.resolve().parents,
            "Use una carpeta externa para el respaldo adicional",
        )
    previous = dict(db.execute("SELECT key,value FROM settings"))
    for key, value in data.model_dump().items():
        db.execute(
            "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value) if value is not None else ""),
        )
    audit(
        db,
        user,
        "update_settings",
        kind="settings",
        before=previous,
        after=data.model_dump(mode="json"),
    )
    return {"ok": True}


@app.get("/api/backups")
def backups(user: User, db: DB):
    admin(user)
    destination = Path(setting(db, "backup_destination") or str(database.DATA / "backups"))
    return [
        {"name": p.name, "size": p.stat().st_size}
        for p in sorted(destination.glob("*.zip"), reverse=True)
    ]


@app.post("/api/backups")
def make_backup(user: User, db: DB):
    admin(user)
    db.commit()
    path = artifacts.backup(user)
    return {"name": path.name}


@app.get("/api/backups/{name}")
def download_backup(name: str, user: User, db: DB):
    admin(user)
    require(Path(name).name == name and name.endswith(".zip"), "Nombre inválido")
    path = Path(setting(db, "backup_destination") or str(database.DATA / "backups")) / name
    require(path.is_file(), "Respaldo no encontrado", 404)
    audit(db, user, "download_backup", kind="backup", after={"name": name})
    return FileResponse(path, filename=name)


@app.post("/api/backups/restore")
def restore_backup(file: UploadFile, user: User, request: Request, db: DB):
    admin(user)
    require(
        request.headers.get("x-confirm-restore") == "RESTAURAR",
        "Debe confirmar la restauración",
        422,
    )
    db.commit()
    with database.LOCK:
        with transaction() as db:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            active = db.execute(
                "SELECT COUNT(*) FROM sessions WHERE last_seen>?", (cutoff,)
            ).fetchone()[0]
            require(active == 1, "Cierre las demás sesiones antes de restaurar", 409)
        content = file.file.read(500_000_001)
        require(len(content) <= 500_000_000, "Respaldo máximo 500 MB")
        return artifacts.restore(content, user)


@app.get("/api/exchange-rate")
def exchange_rate(user: User, db: DB):
    return {"exchange_rate": setting(db, "exchange_rate")}


@app.get("/api/alerts")
def alerts(user: User, db: DB):
    allowed = entities(user, db)
    result = []
    for entity in allowed:
        debt = arrears(db, entity["id"])
        expired = db.execute(
            "SELECT COUNT(*) FROM reservations WHERE entity_id=? AND status='active' AND expires_on<?",
            (entity["id"], str(today(db))),
        ).fetchone()[0]
        result.append(
            {
                "entity_id": entity["id"],
                "entity": entity["name"],
                "overdue_count": sum(r["color"] == "red" for r in debt),
                "upcoming_count": sum(r["color"] == "yellow" for r in debt),
                "expired_reservations": expired,
            }
        )
    return {"items": result, "today": str(today(db))}


@app.post("/api/auth/close-other-sessions")
def close_other_sessions(user: User, request: Request, db: DB):
    admin(user)
    token_hash = hashlib.sha256(request.cookies["gestor_session"].encode()).hexdigest()
    db.execute("DELETE FROM sessions WHERE token_hash<>?", (token_hash,))
    audit(db, user, "close_other_sessions", kind="session")
    return {"ok": True}


@app.get("/api/catalogs/{kind}/template.xlsx")
def catalog_template(kind: str, user: User, db: DB):
    admin(user)
    catalog_io.kind_valid(kind)
    path = Path(__file__).with_name("templates") / (kind + ".xlsx")
    require(path.is_file(), "Plantilla no disponible", 404)
    return FileResponse(
        path, filename=("Plantilla_Clientes.xlsx" if kind == "clients" else "Plantilla_Lotes.xlsx")
    )


@app.get("/api/entities/{entity}/catalogs/{kind}/export.xlsx")
def catalog_export(entity: int, kind: str, user: User, db: DB, q: str = "", state: str = ""):
    catalog_io.kind_valid(kind)
    authorize(db, user, entity)
    content = catalog_io.export_catalog(db, entity, kind, q, state)
    audit(db, user, "export_" + kind, entity, kind="export", after={"search": q, "state": state})
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{kind}-{entity}.xlsx"'},
    )


@app.post("/api/entities/{entity}/catalogs/{kind}/import/preview")
def import_preview(
    entity: int,
    kind: str,
    file: UploadFile,
    user: User,
    db: DB,
    mode: Annotated[str, Form()] = "create",
    reason: Annotated[str, Form()] = "Importación de catálogo",
):
    admin(user)
    catalog_io.kind_valid(kind)
    authorize(db, user, entity, True)
    require(3 <= len(reason.strip()) <= 2000, "Motivo de 3 a 2000 caracteres")
    records = catalog_io.read_file(file.file.read(12_000_001), file.filename or "", kind)
    changes, errors = catalog_io.plan_import(db, entity, kind, records, mode)
    token = (
        None
        if errors
        else admin_data.remember(
            user,
            {
                "purpose": "import",
                "entity": entity,
                "kind": kind,
                "changes": changes,
                "reason": reason,
                "fingerprint": catalog_io.fingerprint(db, entity, kind),
            },
        )
    )
    return {
        "token": token,
        "create": sum(r["operation"] == "create" for r in changes),
        "update": sum(r["operation"] == "update" for r in changes),
        "errors": errors[:100],
        "error_count": len(errors),
        "rows": changes[:100],
        "total": len(records),
    }


@app.post("/api/catalogs/import/execute")
def import_execute(data: m.PreviewConfirm, user: User, db: DB):
    admin(user)
    require(data.confirmation == "IMPORTAR", "Escriba IMPORTAR")
    plan = admin_data.recalled(user, data.token, "import")
    authorize(db, user, plan["entity"], True)
    require(
        plan["fingerprint"] == catalog_io.fingerprint(db, plan["entity"], plan["kind"]),
        "El catálogo cambió; vuelva a obtener la vista previa",
        409,
    )
    db.commit()
    backup = artifacts.backup(user)
    db.execute("BEGIN IMMEDIATE")
    catalog_io.apply_import(db, user, plan["entity"], plan["kind"], plan["changes"], plan["reason"])
    db.commit()
    admin_data.PREVIEWS.pop(data.token, None)
    return {"imported": len(plan["changes"]), "backup": backup.name}


@app.get("/api/admin/database")
def database_info(user: User, db: DB):
    admin(user)
    return {
        "path": str(database.DATA),
        "file": str(database.DATA / "gestor.sqlite3"),
        "tables": admin_data.table_info(db),
        "schema": db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0],
        "environment_override": bool(os.environ.get("GESTOR_DATA_DIR")),
    }


@app.get("/api/admin/database/export.sqlite3")
def database_export(user: User, db: DB):
    admin(user)
    audit(db, user, "export_database", kind="database")
    db.commit()
    snapshot = sqlite3.connect(":memory:")
    try:
        db.backup(snapshot)
        content = snapshot.serialize()
    finally:
        snapshot.close()
    return Response(
        content,
        media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": 'attachment; filename="gestor.sqlite3"'},
    )


@app.post("/api/admin/database/sql/preview")
def sql_preview(data: m.SQLStatement, user: User, db: DB):
    admin(user)
    result = admin_data.sql_operation(db, data.sql)
    result["token"] = (
        admin_data.remember(
            user,
            {
                "purpose": "sql",
                "sql": data.sql,
                "reason": data.reason,
                "tables": result["tables"],
                "fingerprint": admin_data.state_hash(db, result["tables"]),
                "writes": result["writes"],
            },
        )
        if result["writes"]
        else None
    )
    return result


@app.post("/api/admin/database/sql/execute")
def sql_execute(data: m.PreviewConfirm, user: User, db: DB):
    admin(user)
    require(data.confirmation == "EJECUTAR", "Escriba EJECUTAR")
    plan = admin_data.recalled(user, data.token, "sql")
    require(
        plan["fingerprint"] == admin_data.state_hash(db, plan["tables"]),
        "Los datos cambiaron; revise nuevamente la sentencia",
        409,
    )
    db.commit()
    backup = artifacts.backup(user)
    db.execute("BEGIN IMMEDIATE")
    result = admin_data.sql_operation(db, plan["sql"], dry_run=False)
    audit(
        db,
        user,
        "admin_sql",
        kind="database",
        reason=plan["reason"],
        after={
            "sql": plan["sql"],
            "tables": result["tables"],
            "changes": result["changes"],
            "backup": backup.name,
        },
    )
    db.commit()
    admin_data.PREVIEWS.pop(data.token, None)
    return {**result, "backup": backup.name}


@app.post("/api/admin/database/location")
def database_location(data: m.DataLocation, user: User, db: DB):
    admin(user)
    require(data.confirmation == "MOVER", "Escriba MOVER")
    require(
        db.execute(
            "SELECT COUNT(*) FROM sessions WHERE last_seen>?",
            ((datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),),
        ).fetchone()[0]
        == 1,
        "Cierre las demás sesiones antes de mover los datos",
        409,
    )
    db.commit()
    backup = artifacts.backup(user)
    return {**admin_data.relocate(db, user, data.path, data.reason), "backup": backup.name}


STATIC = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if STATIC.exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="frontend")
