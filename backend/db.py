import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
LOCATION_CONFIG = LOCAL / "GrupoAbogados_D_Honduras-location.json"


def configured_data():
    if os.environ.get("GESTOR_DATA_DIR"):
        return Path(os.environ["GESTOR_DATA_DIR"]).resolve()
    if LOCATION_CONFIG.is_file():
        config = json.loads(LOCATION_CONFIG.read_text(encoding="utf-8"))
        location = Path(config["data_dir"])
        if not location.is_absolute() or not (location / "gestor.sqlite3").is_file():
            raise ValueError(
                "Ubicación de datos inválida; revise GrupoAbogados_D_Honduras-location.json"
            )
        return location.resolve()
    return (LOCAL / "GrupoAbogados_D_Honduras").resolve()


DATA = configured_data()
MAINTENANCE = False
LOCK = threading.RLock()
REQUEST_GATE = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(
        DATA / "gestor.sqlite3", timeout=5, isolation_level=None, check_same_thread=False
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def initialize():
    with LOCK:
        db = connect()
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
        migrate(db)
        db.close()


def migrate(db):
    """Upgrade existing v1 databases without replacing any customer records."""
    version = db.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    if version not in (1, 2):
        raise ValueError("Esquema incompatible")
    db.execute("BEGIN IMMEDIATE")
    try:
        columns = {r[1] for r in db.execute("PRAGMA table_info(clients)")}
        if "status" not in columns:
            db.execute(
                "ALTER TABLE clients ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive'))"
            )
        db.execute("DELETE FROM schema_version")
        db.execute("INSERT INTO schema_version VALUES(2)")
        db.commit()
    except BaseException:
        db.rollback()
        raise


@contextmanager
def transaction():
    # Single process plus SQLite BEGIN IMMEDIATE serializes financial operations.
    with LOCK:
        db = connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


def setting(db, key):
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else ""


def today(db):
    return datetime.now(ZoneInfo(setting(db, "timezone"))).date()


def audit(
    db,
    user,
    action,
    entity=None,
    kind=None,
    record=None,
    reason=None,
    before=None,
    after=None,
    result="success",
):
    db.execute(
        "INSERT INTO audit(created_at,user_id,role,entity_id,action,record_type,record_id,result,reason,before_json,after_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            now(),
            user["id"] if user else None,
            user["role"] if user else None,
            entity,
            action,
            kind,
            record,
            result,
            reason,
            json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
            json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
        ),
    )
