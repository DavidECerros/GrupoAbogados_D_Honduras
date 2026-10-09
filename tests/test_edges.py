import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from conftest import create
from test_acceptance import payment

from backend import db as database
from backend.finance import create_payment
from backend.models import Payment


def test_amendment_with_payments_and_void_preserves_balance(portfolio):
    c, e, cl, lot, sale = portfolio
    paid = create(c, "/api/payments", payment(sale, "15000"))
    body = {
        "price": "120000",
        "down_payment": "10000",
        "installments": 6,
        "down_due": "2026-01-31",
        "first_due": "2026-11-30",
        "reason": "Reestructuración de prueba",
    }
    revised = c.put(f"/api/contracts/{sale['id']}", json=body)
    assert revised.status_code == 200, revised.text
    assert revised.json()["balance"] == 10_500_000
    assert c.get(f"/api/contracts/{sale['id']}/versions").json()[0]["version"] == 1
    assert (
        c.post(
            f"/api/payments/{paid['id']}/void", json={"reason": "Reversión posterior"}
        ).status_code
        == 200
    )
    assert c.get(f"/api/contracts/{sale['id']}").json()["balance"] == 12_000_000
    with database.transaction() as db:
        assert (
            sum(
                r[0]
                for r in db.execute(
                    "SELECT amount FROM allocations WHERE payment_id=?", (paid["id"],)
                )
            )
            == 1_500_000
        )
        assert (
            json.loads(db.execute("SELECT snapshot FROM receipts").fetchone()[0])["balance_after"]
            == 8_500_000
        )


def test_amendment_rejects_price_below_paid(portfolio):
    c, e, cl, lot, sale = portfolio
    create(c, "/api/payments", payment(sale, "15000"))
    body = {
        "price": "14000",
        "down_payment": "10000",
        "installments": 6,
        "down_due": "2026-01-31",
        "first_due": "2026-11-30",
        "reason": "Inválido",
    }
    assert c.put(f"/api/contracts/{sale['id']}", json=body).status_code == 422
    assert c.get(f"/api/contracts/{sale['id']}").json()["balance"] == 8_500_000


def test_daily_backup_idle_poll_and_cookie(admin_client):
    c = admin_client
    assert "HttpOnly" in c.cookies.jar._cookies["testserver.local"]["/"]["gestor_session"]._rest
    assert c.get("/api/entities").status_code == 200
    assert len(list((database.DATA / "backups").glob("daily-*.zip"))) == 1
    with database.transaction() as db:
        initial = db.execute("SELECT last_seen FROM sessions").fetchone()[0]
    assert c.get("/api/auth/me", headers={"X-Passive-Request": "1"}).status_code == 200
    with database.transaction() as db:
        assert db.execute("SELECT last_seen FROM sessions").fetchone()[0] == initial
        db.execute("UPDATE sessions SET last_seen='2000-01-01T00:00:00+00:00'")
    assert c.get("/api/auth/me").status_code == 401


def test_empty_entity_deletion_and_archiving(admin_client):
    c = admin_client
    e = create(c, "/api/entities", {"name": "Vacía"})
    assert c.delete(f"/api/entities/{e['id']}").status_code == 200
    e = create(c, "/api/entities", {"name": "Con historia"})
    create(
        c,
        f"/api/entities/{e['id']}/clients",
        {"name": "Ejemplo", "document_type": "DNI", "document": "EJEMPLO", "phone": "000"},
    )
    assert c.delete(f"/api/entities/{e['id']}").status_code == 409
    assert (
        c.put(
            f"/api/entities/{e['id']}",
            json={"name": "Archivada", "currency": "HNL", "status": "archived"},
        ).status_code
        == 200
    )
    assert c.get(f"/api/entities/{e['id']}/clients").status_code == 200
    assert (
        c.post(
            f"/api/entities/{e['id']}/clients",
            json={
                "name": "No permitido",
                "document_type": "DNI",
                "document": "DOS",
                "phone": "000",
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize("amount", ["0", "-1", "0.001", "nan", "inf"])
def test_invalid_money_rejected(portfolio, amount):
    c, e, cl, lot, sale = portfolio
    assert c.post("/api/payments", json=payment(sale, amount)).status_code == 422


def test_bank_reference_and_client_supplied_operator(portfolio):
    c, e, cl, lot, sale = portfolio
    assert c.post("/api/payments", json=payment(sale, "10", method="deposit")).status_code == 422
    assert (
        c.post("/api/payments", json={**payment(sale, "10"), "created_by": 42}).status_code == 422
    )
    assert (
        c.post(
            "/api/payments", json=payment(sale, "10", method="deposit", bank_reference="SINTETICO")
        ).status_code
        == 200
    )


def test_dashboard_separates_currencies_and_void(portfolio):
    c, e, cl, lot, sale = portfolio
    assert c.put("/api/settings", json={"exchange_rate": "25"}).status_code == 200
    first = create(c, "/api/payments", payment(sale, "100"))
    create(c, "/api/payments", payment(sale, "10", "USD"))
    data = c.get("/api/dashboard").json()
    assert {r["currency"]: r["amount"] for r in data["collection"]} == {"HNL": 10000, "USD": 1000}
    c.post(f"/api/payments/{first['id']}/void", json={"reason": "Anulado de prueba"})
    data = c.get("/api/dashboard").json()
    assert {r["currency"]: r["amount"] for r in data["collection"]} == {"USD": 1000}


def test_backup_tamper_does_not_modify_live_data(portfolio):
    c, e, cl, lot, sale = portfolio
    backup = create(c, "/api/backups", {})
    content = c.get(f"/api/backups/{backup['name']}").content
    original = zipfile.ZipFile(io.BytesIO(content))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as tampered:
        for name in original.namelist():
            tampered.writestr(
                name, original.read(name) + (b"alterado" if name == "gestor.sqlite3" else b"")
            )
    response = c.post(
        "/api/backups/restore",
        files={"file": ("alterado.zip", buffer.getvalue())},
        headers={"X-Confirm-Restore": "RESTAURAR"},
    )
    assert response.status_code == 422, response.text
    assert c.get(f"/api/contracts/{sale['id']}").json()["balance"] == 10_000_000


def test_half_letter_receipt(portfolio):
    c, e, cl, lot, sale = portfolio
    assert c.put("/api/settings", json={"paper": "half_letter"}).status_code == 200
    paid = create(c, "/api/payments", payment(sale, "100"))
    response = c.get(f"/api/receipts/{paid['receipt_id']}/pdf")
    assert response.status_code == 200
    assert b"/MediaBox [ 0 0 612 396 ]" in response.content


def test_restore_file_failure_rolls_back_database_and_files(portfolio, monkeypatch):
    from backend import artifacts

    c, e, cl, lot, sale = portfolio
    paid = create(c, "/api/payments", payment(sale, "100"))
    backup = create(c, "/api/backups", {})
    payload = c.get(f"/api/backups/{backup['name']}").content
    create(
        c,
        f"/api/entities/{e['id']}/clients",
        {
            "name": "Conservar tras fallo",
            "document_type": "DNI",
            "document": "FALLO-RESTORE",
            "phone": "000",
        },
    )
    original_replace = artifacts.os.replace
    failed = False

    def simulate_failure(source, destination):
        nonlocal failed
        if not failed and str(destination) == str(database.DATA / "recibos"):
            failed = True
            raise OSError("Fallo de reemplazo simulado")
        return original_replace(source, destination)

    monkeypatch.setattr(artifacts.os, "replace", simulate_failure)
    with pytest.raises(OSError):
        c.post(
            "/api/backups/restore",
            files={"file": ("backup.zip", payload)},
            headers={"X-Confirm-Restore": "RESTAURAR"},
        )
    assert c.get(f"/api/entities/{e['id']}/clients").json()["total"] == 2
    assert c.get(f"/api/contracts/{sale['id']}").json()["balance"] == 9_990_000
    assert c.get(f"/api/receipts/{paid['receipt_id']}/pdf").status_code == 200


def test_simultaneous_folios_and_idempotent_retry(portfolio):
    c, e, cl, lot, sale = portfolio
    with database.transaction() as db:
        user = dict(db.execute("SELECT * FROM users").fetchone())
    shared = Payment(**payment(sale, "1"))

    def charge(body):
        with database.transaction() as db:
            return create_payment(db, user, body)

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(
            pool.map(charge, [shared, shared, *[Payment(**payment(sale, "1")) for _ in range(3)]])
        )
    assert results[0]["id"] == results[1]["id"]
    assert len({r["folio"] for r in results}) == 4
    assert c.get(f"/api/contracts/{sale['id']}").json()["balance"] == 9_999_600


@pytest.mark.parametrize(
    "days,color,category",
    [
        (-5, "green", "al día"),
        (-4, "yellow", "próximo"),
        (0, "yellow", "próximo"),
        (1, "red", "vencido"),
        (30, "red", "vencido"),
        (31, "red", "moroso"),
    ],
)
def test_traffic_light_boundaries(portfolio, days, color, category):
    c, e, cl, lot, sale = portfolio
    current = date.fromisoformat(c.get("/api/auth/me").json()["today"])
    with database.transaction() as db:
        db.execute(
            "UPDATE obligations SET due_date=? WHERE contract_id=?",
            ((current - timedelta(days=days)).isoformat(), sale["id"]),
        )
    item = c.get(f"/api/entities/{e['id']}/arrears").json()["items"][0]
    assert (item["color"], item["category"]) == (color, category)
