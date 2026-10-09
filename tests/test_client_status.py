from datetime import date, timedelta

from conftest import authenticate, create
from test_acceptance import payment

from backend import db as database


def test_inactivate_preserves_history_and_collection(portfolio):
    c, entity, customer, lot, sale = portfolio
    path = f"/api/clients/{customer['id']}/status"
    result = c.patch(path, json={"status": "inactive", "reason": "Cliente duplicado"})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "inactive"
    base = f"/api/entities/{entity['id']}/clients"
    assert c.get(base + "?state=active").json()["total"] == 0
    assert c.get(base + "?state=inactive").json()["items"][0]["id"] == customer["id"]
    assert c.get(base).json()["total"] == 1
    # Inactivation is administrative: existing debts can still be collected.
    paid = create(c, "/api/payments", payment(sale, "10000"))
    assert paid["client_id"] == customer["id"]
    assert c.get(f"/api/contracts/{sale['id']}").json()["client"]["id"] == customer["id"]
    new_lot = create(
        c,
        f"/api/entities/{entity['id']}/lots",
        {"code": "B-02", "price": "100000", "currency": "HNL"},
    )
    reservation = {
        "client_id": customer["id"],
        "lot_id": new_lot["id"],
        "expires_on": str(date.today() + timedelta(days=30)),
    }
    assert c.post(f"/api/entities/{entity['id']}/reservations", json=reservation).status_code == 409
    sale_body = {
        "client_id": customer["id"],
        "lot_id": new_lot["id"],
        "price": "100000",
        "currency": "HNL",
        "down_payment": "10000",
        "installments": 12,
        "down_due": "2026-10-31",
        "first_due": "2026-11-30",
    }
    assert c.post(f"/api/entities/{entity['id']}/contracts", json=sale_body).status_code == 409
    assert (
        c.patch(path, json={"status": "active", "reason": "Reactivar registro"}).status_code == 200
    )
    assert c.post(f"/api/entities/{entity['id']}/reservations", json=reservation).status_code == 200
    with database.transaction() as db:
        actions = [
            r[0]
            for r in db.execute(
                "SELECT action FROM audit WHERE record_type='client' AND record_id=?",
                (customer["id"],),
            )
        ]
        assert "deactivate_client" in actions and "reactivate_client" in actions


def test_only_superuser_can_change_status(portfolio):
    c, entity, customer, lot, sale = portfolio
    create(
        c,
        "/api/users",
        {
            "username": "opstatus",
            "full_name": "Operador prueba",
            "password": "ClaveSeguraPrueba123!",
            "entity_ids": [entity["id"]],
        },
    )
    authenticate(c, "opstatus")
    assert (
        c.post(
            "/api/auth/password",
            json={
                "current_password": "ClaveSeguraPrueba123!",
                "new_password": "OperadorDefinitivo123!",
            },
        ).status_code
        == 200
    )
    assert (
        c.patch(
            f"/api/clients/{customer['id']}/status",
            json={"status": "inactive", "reason": "Prueba permisos"},
        ).status_code
        == 403
    )
    assert c.get(f"/api/entities/{entity['id']}/clients?state=invalid").status_code == 422


def test_migrate_old_database_keeps_clients(portfolio):
    c, entity, customer, lot, sale = portfolio
    with database.transaction() as db:
        db.execute("ALTER TABLE clients DROP COLUMN status")
        db.execute("UPDATE schema_version SET version=1")
    database.initialize()
    database.initialize()
    with database.transaction() as db:
        row = db.execute("SELECT * FROM clients WHERE id=?", (customer["id"],)).fetchone()
        assert row["name"] == customer["name"]
        assert row["status"] == "active"
        assert db.execute("SELECT version FROM schema_version").fetchall()[0][0] == 2


def test_restore_legacy_backup_migrates_clients(portfolio):
    c, entity, customer, lot, sale = portfolio
    with database.transaction() as db:
        db.execute("ALTER TABLE clients DROP COLUMN status")
        db.execute("UPDATE schema_version SET version=1")
    backup = create(c, "/api/backups", {})
    payload = c.get(f"/api/backups/{backup['name']}").content
    database.initialize()
    result = c.post(
        "/api/backups/restore",
        files={"file": ("legacy.zip", payload, "application/zip")},
        headers={"x-confirm-restore": "RESTAURAR"},
    )
    assert result.status_code == 200, result.text
    authenticate(c)
    records = c.get(f"/api/entities/{entity['id']}/clients?state=active").json()
    assert records["total"] == 1
    assert records["items"][0]["id"] == customer["id"]
