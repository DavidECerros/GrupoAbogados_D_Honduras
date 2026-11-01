import io
import json

from conftest import authenticate, create
from openpyxl import load_workbook

from backend import catalog_io
from backend import db as database


def deed(**changes):
    return {
        "code": "ESCRITURA-01",
        "deed_client_name": "Cliente según escritura",
        "deed_client_document": "0000-PRUEBA",
        "deed_address": "Lotificación de prueba, bloque A.\nDirección literal de la escritura.",
        "boundaries": [
            {
                "side": "Norte",
                "bearing": "N 75°07′08″ O",
                "distance": "26.1250",
                "neighbor": "Con lote número 9",
            },
            {"side": "Sur", "distance": "26.00", "neighbor": "Con calle pública"},
        ],
        **changes,
    }


def test_deed_persists_edits_without_changing_contract(portfolio):
    c, e, customer, lot, sale = portfolio
    account = c.get(f"/api/contracts/{sale['id']}").json()
    r = c.put(
        f"/api/lots/{lot['id']}", json=deed(code=lot["code"], registered_client_id=customer["id"])
    )
    assert r.status_code == 200, r.text
    assert r.json()["deed_client_name"] == "Cliente según escritura"
    assert r.json()["price"] == lot["price"]
    r = c.put(
        f"/api/lots/{lot['id']}",
        json={"code": lot["code"], "deed_address": "Dirección corregida\nSegunda línea"},
    )
    assert r.status_code == 200, r.text
    saved = c.get(f"/api/entities/{e['id']}/lots?q=0000-PRUEBA").json()["items"][0]
    assert saved["deed_address"] == "Dirección corregida\nSegunda línea"
    assert saved["boundaries"][0]["distance"] == "26.1250"
    assert saved["registered_client_id"] == customer["id"]
    after = c.get(f"/api/contracts/{sale['id']}").json()
    account.pop("lot")
    after.pop("lot")
    assert after == account


def test_unpriced_deed_cannot_be_sold_until_master_sets_price(portfolio):
    c, e, customer, _, _ = portfolio
    lot = create(c, f"/api/entities/{e['id']}/lots", deed())
    assert lot["price"] is None and lot["pricing_pending"] == 1
    assert c.get(f"/api/lots/{lot['id']}/quote").status_code == 409
    sale = {
        "lot_id": lot["id"],
        "client_id": customer["id"],
        "price": "0.01",
        "currency": "HNL",
        "down_payment": "0",
        "installments": 1,
        "down_due": "2026-11-01",
        "first_due": "2026-11-01",
    }
    assert c.post(f"/api/entities/{e['id']}/contracts", json=sale).status_code == 409
    r = c.put(f"/api/lots/{lot['id']}", json={"code": lot["code"], "price": "250000"})
    assert r.status_code == 200, r.text
    assert r.json()["deed_address"] == lot["deed_address"]
    q = c.get(f"/api/lots/{lot['id']}/quote").json()
    assert q["price"] == 25000000
    create(c, f"/api/entities/{e['id']}/contracts", {**sale, "price": "250000"})


def test_client_reference_is_scoped_and_protected_from_purge(portfolio):
    c, e, customer, _, _ = portfolio
    other = create(c, "/api/entities", {"name": "Otra lotificadora"})
    r = c.post(f"/api/entities/{other['id']}/lots", json=deed(registered_client_id=customer["id"]))
    assert r.status_code == 403
    linked = create(
        c,
        f"/api/entities/{e['id']}/clients",
        {
            "name": "Cliente vinculado",
            "document_type": "DNI",
            "document": "VINCULO-001",
            "phone": "00000000",
        },
    )
    lot = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "VINCULO", "registered_client_id": linked["id"]},
    )
    assert lot["deed_client_name"] == linked["name"]
    create(
        c,
        f"/api/clients/{linked['id']}/lifecycle",
        {"action": "delete", "reason": "Prueba de referencia"},
    )
    assert (
        c.post(
            f"/api/clients/{linked['id']}/lifecycle",
            json={"action": "purge", "reason": "Prueba de referencia"},
        ).status_code
        == 409
    )
    assert (
        c.put(
            f"/api/lots/{lot['id']}",
            json={"code": lot["code"], "deed_address": "Corrección conservando referencia"},
        ).status_code
        == 200
    )


def test_deed_import_roundtrip_and_legacy_columns_preserve_fields(portfolio):
    c, e, _, _, _ = portfolio
    lot = create(c, f"/api/entities/{e['id']}/lots", deed())
    payload = c.get(f"/api/entities/{e['id']}/catalogs/lots/export.xlsx?q=ESCRITURA").content
    records = catalog_io.read_file(payload, "lotes.xlsx", "lots")
    with database.transaction() as db:
        changes, errors = catalog_io.plan_import(db, e["id"], "lots", records, "upsert")
        assert not errors, errors
        catalog_io.apply_import(
            db, {"id": 1, "role": "superuser"}, e["id"], "lots", changes, "Roundtrip"
        )
        saved = dict(db.execute("SELECT * FROM lots WHERE id=?", (lot["id"],)).fetchone())
        assert json.loads(saved["boundaries"])[0]["neighbor"] == "Con lote número 9"
        assert saved["pricing_pending"] == 1
        legacy = [
            (
                2,
                {
                    "id": lot["id"],
                    "code": lot["code"],
                    "description": "Importación antigua",
                    "price": "250000",
                    "currency": "HNL",
                    "status": "Disponible",
                },
            )
        ]
        changes, errors = catalog_io.plan_import(db, e["id"], "lots", legacy, "upsert")
        assert not errors, errors
        catalog_io.apply_import(
            db, {"id": 1, "role": "superuser"}, e["id"], "lots", changes, "Formato anterior"
        )
        after = dict(db.execute("SELECT * FROM lots WHERE id=?", (lot["id"],)).fetchone())
        assert after["boundaries"] == saved["boundaries"]
        assert after["deed_address"] == saved["deed_address"]
    book = load_workbook(io.BytesIO(c.get("/api/catalogs/lots/template.xlsx").content))
    assert "Dirección según escritura" in [cell.value for cell in book["Lotes"][1]]


def test_invalid_boundaries_are_rejected(portfolio):
    c, e, _, _, _ = portfolio
    url = f"/api/entities/{e['id']}/lots"
    assert (
        c.post(
            url, json=deed(boundaries=[{"side": "Norte", "distance": "-1", "neighbor": "Calle"}])
        ).status_code
        == 422
    )
    sides = [
        {"side": "Norte", "distance": "1", "neighbor": "Calle"},
        {"side": "norte", "distance": "2", "neighbor": "Lote"},
    ]
    assert c.post(url, json=deed(boundaries=sides)).status_code == 422


def test_operator_can_capture_deed_but_cannot_set_price(portfolio):
    c, e, _, _, _ = portfolio
    create(
        c,
        "/api/users",
        {
            "username": "deedop",
            "full_name": "Captura prueba",
            "password": "ClaveSeguraPrueba123!",
            "entity_ids": [e["id"]],
            "permissions": {"lots": "write"},
        },
    )
    authenticate(c, "deedop")
    assert (
        c.post(
            "/api/auth/password",
            json={
                "current_password": "ClaveSeguraPrueba123!",
                "new_password": "NuevaClavePrueba123!",
            },
        ).status_code
        == 200
    )
    lot = create(c, f"/api/entities/{e['id']}/lots", deed())
    assert (
        c.put(
            f"/api/lots/{lot['id']}",
            json={"code": lot["code"], "deed_address": "Dirección corregida"},
        ).status_code
        == 200
    )
    assert (
        c.put(f"/api/lots/{lot['id']}", json={"code": lot["code"], "price": "250000"}).status_code
        == 403
    )
