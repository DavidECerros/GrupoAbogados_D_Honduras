"""Synthetic browser QA only; never initializes the user's production installation."""

import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
target = ROOT / "qa" / "browser-data"
os.environ["GESTOR_DATA_DIR"] = str(target)


def main():
    from backend.app import HASHER
    from backend.db import initialize, now, today, transaction
    from backend.finance import create_sale
    from backend.models import Sale

    initialize()
    with transaction() as db:
        if db.execute("SELECT 1 FROM users").fetchone():
            return
        user_id = db.execute(
            "INSERT INTO users(username,full_name,password_hash,role,created_at) VALUES(?,?,?,'superuser',?)",
            ("qa_admin", "Administrador de prueba", HASHER.hash("SoloPruebasUI123!"), now()),
        ).lastrowid
        user = dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        for entity_name in ("Los Robles · DEMO", "Valle Verde · DEMO"):
            entity = db.execute(
                "INSERT INTO entities(name,currency) VALUES(?,?)", (entity_name, "HNL")
            ).lastrowid
            for index in range(1, 9):
                names = [
                    "Cliente demo Ana",
                    "Cliente demo Carlos",
                    "Cliente demo Sofía",
                    "Cliente demo Miguel",
                ]
                client = db.execute(
                    "INSERT INTO clients(entity_id,name,document_type,document,phone,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        entity,
                        names[(index - 1) % 4] + f" {index}",
                        "DEMO",
                        f"DEMO-{entity}-{index}",
                        "0000-0000",
                        user_id,
                        now(),
                    ),
                ).lastrowid
                lot = db.execute(
                    "INSERT INTO lots(entity_id,code,description,price,currency) VALUES(?,?,?,?,?)",
                    (entity, f"A-{index:02}", "Sector norte · 250 m²", 12500000, "HNL"),
                ).lastrowid
                if index <= 4:
                    create_sale(
                        db,
                        user,
                        entity,
                        Sale(
                            lot_id=lot,
                            client_id=client,
                            price="125000",
                            currency="HNL",
                            down_payment="15000",
                            installments=24,
                            down_due=today(db) - timedelta(days=15 * index),
                            first_due=today(db) + timedelta(days=10),
                        ),
                    )
    print("Datos sintéticos preparados en qa/browser-data; usuario qa_admin.")


if __name__ == "__main__":
    main()
