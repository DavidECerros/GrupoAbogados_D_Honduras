"""Local administrative recovery; server must be stopped. Never exposed by API."""

import getpass
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from argon2 import PasswordHasher

from backend.db import audit, initialize, transaction


def main():
    # The launcher uses port 8000 by default. A custom port must be supplied locally.
    port = int(os.environ.get("GESTOR_RECOVERY_PORT", "8000"))
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit("Cierre el servidor antes de recuperar el superusuario.")
    password = getpass.getpass("Nueva contraseña del superusuario (12 caracteres mínimo): ")
    if len(password) < 12 or password != getpass.getpass("Repita la contraseña: "):
        raise SystemExit("Contraseña inválida o no coincide.")
    reason = input("Motivo de recuperación administrativa: ").strip()
    if len(reason) < 3:
        raise SystemExit("Debe indicar el motivo.")
    initialize()
    with transaction() as db:
        user = db.execute("SELECT * FROM users WHERE role='superuser' AND active=1").fetchone()
        if not user:
            raise SystemExit("No hay superusuario. Use la configuración inicial.")
        db.execute(
            "UPDATE users SET password_hash=?,must_change=1,failures=0,locked_until=NULL WHERE id=?",
            (
                PasswordHasher(time_cost=3, memory_cost=19456, parallelism=1).hash(password),
                user["id"],
            ),
        )
        db.execute("DELETE FROM sessions")
        audit(db, dict(user), "recover_superuser", kind="user", record=user["id"], reason=reason)
    print("Contraseña recuperada. Sesiones revocadas; se exigirá cambio al ingresar.")


if __name__ == "__main__":
    main()
