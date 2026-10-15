import json
from decimal import Decimal

from conftest import create
from test_land_features import operator, rectangle, sale_data

from backend import db as database


def test_entities_archive_users_disable_and_approval_withdraw(portfolio):
    c, e, customer, lot, sale = portfolio
    assert call(c, "entities", e).status_code == 200
    assert c.get(f"/api/contracts/{sale['id']}").status_code == 200
    assert call(c, "entities", e, "restore").status_code == 200
    user = create(
        c,
        "/api/users",
        {
            "username": "desactivar",
            "full_name": "Prueba de baja",
            "password": "ClaveTemporalPrueba123!",
            "entity_ids": [e["id"]],
        },
    )
    result = call(c, "users", user)
    assert result.status_code == 200, result.text
    assert "password_hash" not in result.json()["record"]
    assert call(c, "users", user, "restore").status_code == 200
    master = c.get("/api/auth/me").json()["user"]
    assert call(c, "users", master).status_code == 409
    request = create(
        c,
        f"/api/entities/{e['id']}/approvals",
        {
            "action": "amend_contract",
            "record_id": sale["id"],
            "reason": "Corrección propuesta",
            "payload": {
                "price": "100000",
                "down_payment": "10000",
                "installments": 12,
                "down_due": "2026-10-14",
                "first_due": "2026-11-14",
            },
        },
    )
    assert (
        c.put(f"/api/approvals/{request['id']}", json={"reason": "Motivo actualizado"}).status_code
        == 200
    )
    assert call(c, "approvals", request).status_code == 200
    assert (
        c.post(
            f"/api/approvals/{request['id']}/resolve",
            json={"approve": True, "reason": "No debe ejecutar"},
        ).status_code
        == 409
    )


def test_contract_repeated_modifications_preserve_single_down_payment(portfolio):
    c, e, customer, lot, sale = portfolio
    for price in ("150000", "250000"):
        response = c.put(
            f"/api/contracts/{sale['id']}",
            json={
                "price": price,
                "down_payment": "10000",
                "installments": 12,
                "down_due": "2026-10-14",
                "first_due": "2026-11-14",
                "reason": "Corrección de condiciones",
            },
        )
        assert response.status_code == 200, response.text
    statement = c.get(f"/api/contracts/{sale['id']}").json()
    assert sum(o["amount"] for o in statement["obligations"] if o["number"] > 0) == 24000000
    assert len(c.get(f"/api/contracts/{sale['id']}/versions").json()) == 2


def call(c, kind, record, action="delete"):
    return c.post(
        f"/api/{kind}/{record['id']}/lifecycle",
        json={"action": action, "reason": "Corrección de prueba"},
    )


def tariff(c, e, m2, v2=None):
    response = c.put(
        f"/api/entities/{e['id']}/land-prices",
        json={"price_m2": m2, "price_v2": v2, "currency": "HNL"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_independent_entity_rates_and_unchanged_quotes(portfolio):
    c, e, customer, *_ = portfolio
    other = create(c, "/api/entities", {"name": "Lotificadora B"})
    tariff(c, e, "1000", "700")
    tariff(c, other, "2000", "1400")
    a = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "A-AREA", "area_m2": "155", "pricing_unit": "m2"},
    )
    b = create(
        c,
        f"/api/entities/{other['id']}/lots",
        {"code": "B-AREA", "area_m2": "155", "pricing_unit": "m2"},
    )
    qa = c.get(f"/api/lots/{a['id']}/quote").json()
    qb = c.get(f"/api/lots/{b['id']}/quote").json()
    assert qa["price"] == 15500000 and qb["price"] == 31000000
    tariff(c, other, "2500")
    assert c.get(f"/api/lots/{a['id']}/quote").json() == qa
    sold = create(c, f"/api/entities/{e['id']}/contracts", sale_data(a, customer, qa))
    tariff(c, e, "3000")
    account = c.get(f"/api/contracts/{sold['id']}").json()
    assert account["price"] == 15500000
    assert json.loads(account["pricing_snapshot"])["entity_id"] == e["id"]


def test_repeat_lot_edit_and_250000_minus_10000(portfolio):
    c, e, customer, *_ = portfolio
    tariff(c, e, "1548.39")
    lot = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "PRECIO", "price": "250000", "area_m2": "155", "pricing_unit": "m2"},
    )
    assert c.get(f"/api/lots/{lot['id']}/quote").json()["price"] == 24000045
    for amount in ("260000", "250000"):
        response = c.put(
            f"/api/lots/{lot['id']}",
            json={
                "code": "PRECIO",
                "description": "Edición " + amount,
                "price": amount,
                "area_m2": "155",
                "pricing_unit": "fixed",
            },
        )
        assert response.status_code == 200, response.text
    q = c.get(f"/api/lots/{lot['id']}/quote").json()
    assert q["price"] == 25000000
    body = {**sale_data(lot, customer, q), "down_payment": "10000"}
    sale = create(c, f"/api/entities/{e['id']}/contracts", body)
    statement = c.get(f"/api/contracts/{sale['id']}").json()
    installments = [o for o in statement["obligations"] if o["number"] > 0]
    assert sum(o["amount"] for o in installments) == 24000000
    assert sum(o["amount"] for o in statement["obligations"]) == 25000000
    assert statement["balance"] == 25000000


def test_repeated_client_edits_and_reversible_removal(portfolio):
    c, e, customer, lot, sale = portfolio
    for phone in ("11111111", "22222222"):
        body = {
            k: customer[k] for k in ("name", "document_type", "document", "phone", "email", "notes")
        }
        body["phone"] = phone
        result = c.put(f"/api/clients/{customer['id']}", json=body)
        assert result.status_code == 200, result.text
    assert call(c, "clients", customer).status_code == 200
    assert c.get(f"/api/entities/{e['id']}/clients").json()["total"] == 0
    assert (
        c.get(f"/api/entities/{e['id']}/clients?view=deleted").json()["items"][0]["phone"]
        == "22222222"
    )
    assert c.get(f"/api/contracts/{sale['id']}").json()["client"]["id"] == customer["id"]
    assert call(c, "clients", customer, "restore").status_code == 200
    assert c.get(f"/api/entities/{e['id']}/clients").json()["total"] == 1
    assert call(c, "lots", lot).status_code == 200
    assert c.get(f"/api/entities/{e['id']}/lots").json()["total"] == 0
    assert c.get(f"/api/contracts/{sale['id']}").status_code == 200
    assert call(c, "lots", lot, "restore").status_code == 200


def test_cancel_contract_requires_explicit_payment_void(portfolio):
    c, e, customer, lot, sale = portfolio
    payment = create(
        c,
        "/api/payments",
        {
            "operation_id": "correction-operation-123",
            "contract_id": sale["id"],
            "amount": "100",
            "currency": "HNL",
        },
    )
    assert call(c, "contracts", sale).status_code == 409
    assert call(c, "payments", payment).status_code == 200
    assert call(c, "contracts", sale).status_code == 200
    assert c.get(f"/api/entities/{e['id']}/contracts").json()["total"] == 0
    assert c.get(f"/api/entities/{e['id']}/contracts?view=deleted").json()["total"] == 1
    assert (
        c.post(
            "/api/payments",
            json={
                "operation_id": "cancelled-operation-123",
                "contract_id": sale["id"],
                "amount": "1",
                "currency": "HNL",
            },
        ).status_code
        == 409
    )
    assert call(c, "contracts", sale, "restore").status_code == 200
    assert c.get(f"/api/contracts/{sale['id']}").json()["status"] == "active"


def test_edit_reservation_twice_and_release_on_removal(portfolio):
    c, e, customer, *_ = portfolio
    first = create(c, f"/api/entities/{e['id']}/lots", {"code": "RESERVA1", "price": "1"})
    second = create(c, f"/api/entities/{e['id']}/lots", {"code": "RESERVA2", "price": "1"})
    with database.transaction() as db:
        future = str(database.today(db).replace(year=database.today(db).year + 1))
    body = {"lot_id": first["id"], "client_id": customer["id"], "expires_on": future}
    reservation = create(c, f"/api/entities/{e['id']}/reservations", body)
    for identifier in (second["id"], first["id"]):
        result = c.put(
            f"/api/reservations/{reservation['id']}", json={**body, "lot_id": identifier}
        )
        assert result.status_code == 200, result.text
    assert call(c, "reservations", reservation).status_code == 200
    assert c.get(f"/api/entities/{e['id']}/reservations").json()["total"] == 0
    assert (
        c.get(f"/api/entities/{e['id']}/lots?q=RESERVA1").json()["items"][0]["status"]
        == "available"
    )
    assert call(c, "reservations", reservation, "restore").status_code == 200
    assert c.get(f"/api/entities/{e['id']}/reservations").json()["items"][0]["status"] == "released"


def test_edit_payment_metadata_preserves_balance_and_folio(portfolio):
    c, e, customer, lot, sale = portfolio
    p = create(
        c,
        "/api/payments",
        {
            "operation_id": "metadata-operation-123",
            "contract_id": sale["id"],
            "amount": "100",
            "currency": "HNL",
        },
    )
    with database.transaction() as db:
        day = str(database.today(db))
    for note in ("Primera corrección", "Segunda corrección"):
        result = c.put(
            f"/api/payments/{p['id']}",
            json={
                "payment_date": day,
                "method": "transfer",
                "bank_reference": "BANCO-PRUEBA",
                "notes": note,
                "reason": "Corregir referencia",
            },
        )
        assert result.status_code == 200, result.text
    assert result.json()["received"] == p["received"]
    assert c.get(f"/api/contracts/{sale['id']}").json()["balance"] == sale["price"] - p["applied"]
    assert c.get(f"/api/receipts/{p['receipt_id']}/pdf").status_code == 200
    with database.transaction() as db:
        receipt = db.execute("SELECT * FROM receipts WHERE id=?", (p["receipt_id"],)).fetchone()
        assert receipt["folio"] == p["folio"]
        assert json.loads(receipt["snapshot"])["bank_reference"] == "BANCO-PRUEBA"


def test_plan_repeated_edit_archive_restore(portfolio):
    c, e, customer, lot, *_ = portfolio
    data = rectangle(lot_id=lot["id"])
    plan = create(c, f"/api/entities/{e['id']}/plans", data)
    for note in ("Primera versión", "Segunda versión"):
        result = c.put(f"/api/plans/{plan['id']}", json={**data, "notes": note})
        assert result.status_code == 200, result.text
    assert c.get(f"/api/plans/{plan['id']}").json()["payload"]["notes"] == "Segunda versión"
    assert call(c, "plans", plan).status_code == 200
    assert c.get(f"/api/entities/{e['id']}/plans").json()["total"] == 0
    assert call(c, "plans", plan, "restore").status_code == 200
    assert c.get(f"/api/entities/{e['id']}/plans").json()["total"] == 1


def test_tariffs_and_removal_require_master(portfolio):
    c, e, customer, lot, sale = portfolio
    operator(c, e, profile="administrator")
    assert (
        c.put(f"/api/entities/{e['id']}/land-prices", json={"price_m2": "999"}).status_code == 403
    )
    assert call(c, "lots", lot).status_code == 403


def test_v3_rates_copied_once_and_not_shared(portfolio):
    c, e, *_ = portfolio
    with database.transaction() as db:
        db.execute("DROP TABLE entity_prices")
        db.execute("UPDATE settings SET value='1548.39' WHERE key='price_m2'")
        db.execute("UPDATE schema_version SET version=3")
    database.initialize()
    assert Decimal(c.get(f"/api/entities/{e['id']}/land-prices").json()["price_m2"]) == Decimal(
        "1548.39"
    )
    tariff(c, e, "2000")
    with database.transaction() as db:
        db.execute("UPDATE settings SET value='3000' WHERE key='price_m2'")
    database.initialize()
    assert c.get(f"/api/entities/{e['id']}/land-prices").json()["price_m2"] == "2000"
