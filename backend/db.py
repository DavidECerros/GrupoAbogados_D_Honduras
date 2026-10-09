import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(
    os.environ.get(
        "GESTOR_DATA_DIR",
        str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GrupoAbogados_D_Honduras"),
    )
).resolve()
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
        db.close()


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
