import json
from decimal import Decimal

import pytest
from conftest import authenticate, create
from fastapi import HTTPException
from pyproj import Transformer

from backend import db as database
from backend.land_plans import Plan, geometry


def rates(c, **values):
    current = c.get("/api/settings").json()
    allowed = {
        "timezone",
        "exchange_rate",
        "paper",
        "backup_destination",
        "price_m2",
        "price_v2",
        "land_currency",
        "vara_m2",
    }
    body = {k: v for k, v in current.items() if k in allowed}
    for key in ("exchange_rate", "price_m2", "price_v2"):
        if not body.get(key):
            body[key] = None
    body.update(values)
    result = c.put("/api/settings", json=body)
    assert result.status_code == 200, result.text
    for entity in c.get("/api/entities").json():
        old = c.get(f"/api/entities/{entity['id']}/land-prices").json()
        scoped = {k: old.get(k) for k in ("price_m2", "price_v2", "currency")}
        for key in ("price_m2", "price_v2"):
            if key in values:
                scoped[key] = values[key]
        if "land_currency" in values:
            scoped["currency"] = values["land_currency"]
        response = c.put(f"/api/entities/{entity['id']}/land-prices", json=scoped)
        assert response.status_code == 200, response.text


def sale_data(lot, customer, q):
    return {
        "lot_id": lot["id"],
        "client_id": customer["id"],
        "price": str(Decimal(q["price"]) / 100),
        "currency": q["currency"],
        "quote_token": q["quote_token"],
        "down_payment": "0",
        "installments": 12,
        "down_due": "2026-10-14",
        "first_due": "2026-11-14",
    }


def operator(c, entity, permissions=None, profile="standard"):
    body = {
        "username": "landop",
        "full_name": "Usuario de prueba",
        "password": "ClaveSeguraPrueba123!",
        "entity_ids": [entity["id"]],
        "profile": profile,
    }
    if permissions is not None:
        body["permissions"] = permissions
    user = create(c, "/api/users", body)
    authenticate(c, "landop")
    result = c.post(
        "/api/auth/password",
        json={"current_password": "ClaveSeguraPrueba123!", "new_password": "DefinitivaPrueba123!"},
    )
    assert result.status_code == 200, result.text
    return user


def rectangle(**values):
    return {
        "owner": "Propietario de prueba",
        "location": "Santa Bárbara, Honduras",
        "vertices": [
            {"x": 0, "y": 0, "neighbor": "Sur"},
            {"x": 23.25, "y": 0, "neighbor": "Este"},
            {"x": 23.25, "y": 5, "neighbor": "Norte"},
            {"x": 0, "y": 5, "neighbor": "Oeste"},
        ],
        **values,
    }


def test_area_rates_and_contract_snapshot(portfolio):
    c, e, customer, _, _ = portfolio
    rates(c, price_m2="1000.1234", price_v2="700", land_currency="USD")
    lot = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "AREA", "area_m2": "116.25", "pricing_unit": "m2"},
    )
    q = c.get(f"/api/lots/{lot['id']}/quote").json()
    assert q["price"] == 11626435 and q["currency"] == "USD"
    body = sale_data(lot, customer, q)
    bad = c.post(f"/api/entities/{e['id']}/contracts", json={**body, "price": "1"})
    assert bad.status_code == 409
    sold = create(c, f"/api/entities/{e['id']}/contracts", body)
    snapshot = json.loads(sold["pricing_snapshot"])
    assert snapshot["area_m2"] == "116.25"
    rates(c, price_m2="2000")
    account = c.get(f"/api/contracts/{sold['id']}").json()
    assert account["price"] == 11626435
    assert json.loads(account["pricing_snapshot"]) == snapshot


def test_varas_conversion_and_stale_quote(portfolio):
    c, e, customer, _, _ = portfolio
    rates(c, price_v2="100", vara_m2="0.697224")
    lot = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "VARAS", "area_v2": "100", "pricing_unit": "v2"},
    )
    assert Decimal(lot["area_m2"]) == Decimal("69.722400")
    q = c.get(f"/api/lots/{lot['id']}/quote").json()
    assert q["price"] == 1000000
    rates(c, price_v2="101")
    response = c.post(f"/api/entities/{e['id']}/contracts", json=sale_data(lot, customer, q))
    assert response.status_code == 409
    with database.transaction() as db:
        assert (
            db.execute("SELECT status FROM lots WHERE id=?", (lot["id"],)).fetchone()[0]
            == "available"
        )


def test_missing_rate_and_inconsistent_areas(portfolio):
    c, e, *_ = portfolio
    lot = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "SIN-TARIFA", "area_m2": "50", "pricing_unit": "m2"},
    )
    assert c.get(f"/api/lots/{lot['id']}/quote").status_code == 409
    assert (
        c.post(
            f"/api/entities/{e['id']}/lots", json={"code": "BAD", "area_m2": "1", "area_v2": "100"}
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/api/entities/{e['id']}/lots", json={"code": "EMPTY", "pricing_unit": "m2"}
        ).status_code
        == 422
    )


def test_read_only_and_disabled_modules_enforced(portfolio):
    c, e, customer, lot, contract = portfolio
    operator(c, e, {"lots": "read", "contracts": "read"})
    assert c.get(f"/api/entities/{e['id']}/lots").status_code == 200
    assert c.get(f"/api/entities/{e['id']}/clients").status_code == 403
    assert c.get(f"/api/entities/{e['id']}/catalogs/clients/export.xlsx").status_code == 403
    assert (
        c.post(f"/api/entities/{e['id']}/lots", json={"code": "DENIED", "price": "1"}).status_code
        == 403
    )
    assert (
        c.post(
            "/api/payments",
            json={
                "contract_id": contract["id"],
                "operation_id": "permission-test-123",
                "amount": "1",
                "currency": "HNL",
            },
        ).status_code
        == 403
    )
    for path in ("/api/settings", "/api/admin/database", "/api/users", "/api/backups"):
        assert c.get(path).status_code == 403


def test_administrator_is_scoped_and_cannot_set_rates(portfolio):
    c, e, *_ = portfolio
    other = create(c, "/api/entities", {"name": "Otra entidad"})
    operator(c, e, profile="administrator")
    create(c, f"/api/entities/{e['id']}/lots", {"code": "ADMIN", "price": "1"})
    assert c.get(f"/api/entities/{other['id']}/lots").status_code == 403
    assert c.get(f"/api/dashboard?entity={e['id']}").status_code == 200
    assert c.get("/api/dashboard").status_code == 403
    assert c.put("/api/settings", json={"price_m2": "5"}).status_code == 403
    assert (
        c.post(
            "/api/users",
            json={
                "username": "escalada",
                "full_name": "Escalada",
                "password": "DefinitivaPrueba123!",
            },
        ).status_code
        == 403
    )


def test_permissions_revoked_apply_to_open_session(portfolio):
    c, e, *_ = portfolio
    user = operator(c, e, profile="administrator")
    with database.transaction() as db:
        db.execute(
            "UPDATE users SET permissions=? WHERE id=?", (json.dumps({"lots": "none"}), user["id"])
        )
    assert c.get(f"/api/entities/{e['id']}/lots").status_code == 403


def test_invalid_module_rejected_and_master_protected(portfolio):
    c, *_ = portfolio
    result = c.post(
        "/api/users",
        json={
            "username": "badmodule",
            "full_name": "Bad",
            "password": "DefinitivaPrueba123!",
            "permissions": {"database": "write"},
        },
    )
    assert result.status_code == 422
    me = c.get("/api/auth/me").json()["user"]
    c.put(
        f"/api/users/{me['id']}",
        json={
            "full_name": me["full_name"],
            "active": True,
            "entity_ids": [],
            "profile": "standard",
            "permissions": {"lots": "none"},
        },
    )
    assert c.get("/api/auth/me").json()["user"]["permissions"]["lots"] == "write"


def test_plan_rectangle_pdf_and_geojson(portfolio):
    c, e, _, lot, _ = portfolio
    data = rectangle(lot_id=lot["id"])
    preview = create(c, f"/api/entities/{e['id']}/plans/preview", data)
    assert preview["area_m2"] == 116.25
    assert round(preview["area_v2"], 2) == 166.73
    result = create(c, f"/api/entities/{e['id']}/plans", data)
    pdf = c.get(f"/api/plans/{result['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert c.get(f"/api/plans/{result['id']}/geojson").status_code == 409
    assert c.get(f"/api/entities/{e['id']}/plans").json()["total"] == 1


@pytest.mark.parametrize("longitude,epsg", [(-87.2, 32616), (-83.7, 32617)])
def test_plan_utm_and_gps_round_trip(longitude, epsg):
    transform = Transformer.from_crs(4326, epsg, always_xy=True)
    x, y = transform.transform(longitude, 14.1)
    data = rectangle(crs=f"EPSG:{epsg}")
    for v in data["vertices"]:
        v["x"] += x
        v["y"] += y
    utm = geometry(Plan(**data), Decimal(".697224"))
    back = Transformer.from_crs(epsg, 4326, always_xy=True)
    data["crs"] = "EPSG:4326"
    data["vertices"] = [
        {"x": back.transform(v["x"], v["y"])[0], "y": back.transform(v["x"], v["y"])[1]}
        for v in data["vertices"]
    ]
    gps = geometry(Plan(**data), Decimal(".697224"))
    assert abs(utm["area_m2"] - gps["area_m2"]) < 0.0001
    assert len(gps["geographic"]) == 4


def test_rumbos_and_closure():
    data = rectangle(
        mode="bearings",
        sides=[
            {"bearing": "90", "distance": 23.25},
            {"bearing": "0", "distance": 5},
            {"bearing": "N90W", "distance": 23.25},
            {"bearing": "180", "distance": 5},
        ],
    )
    result = geometry(Plan(**data), Decimal(".697224"))
    assert result["area_m2"] == 116.25 and result["closure_error"] == 0
    data["sides"][-1]["distance"] = 6
    with pytest.raises(HTTPException):
        geometry(Plan(**data), Decimal(".697224"))


@pytest.mark.parametrize(
    "vertices",
    [
        [{"x": 0, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 10}, {"x": 10, "y": 0}],
        [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 2}],
        [{"x": 0, "y": 0}, {"x": 0, "y": 0}, {"x": 1, "y": 1}],
    ],
)
def test_bad_polygons_rejected(vertices):
    with pytest.raises(HTTPException):
        geometry(Plan(**rectangle(vertices=vertices)), Decimal(".697224"))


def test_plans_permissions_and_entity_isolation(portfolio):
    c, e, *_ = portfolio
    other = create(c, "/api/entities", {"name": "Otra entidad"})
    otherlot = create(c, f"/api/entities/{other['id']}/lots", {"code": "OTRO", "price": "1"})
    otherclient = create(
        c,
        f"/api/entities/{other['id']}/clients",
        {"name": "Otro", "document_type": "DEMO", "document": "OTRO", "phone": "0"},
    )
    plan = create(
        c,
        f"/api/entities/{other['id']}/plans",
        rectangle(lot_id=otherlot["id"], client_id=otherclient["id"]),
    )
    operator(c, e, {"plans": "read"})
    assert c.get(f"/api/plans/{plan['id']}/pdf").status_code == 403
    assert c.post(f"/api/entities/{e['id']}/plans", json=rectangle()).status_code == 403
    assert c.get(f"/api/entities/{e['id']}/plans").status_code == 200


def test_lot_export_import_preserves_area_and_old_template(portfolio):
    c, e, *_ = portfolio
    rates(c, price_m2="1000")
    lot = create(
        c,
        f"/api/entities/{e['id']}/lots",
        {"code": "ROUNDTRIP", "price": "5", "area_m2": "116.25", "pricing_unit": "m2"},
    )
    exported = c.get(f"/api/entities/{e['id']}/catalogs/lots/export.xlsx?q=ROUNDTRIP").content
    result = c.post(
        f"/api/entities/{e['id']}/catalogs/lots/import/preview",
        files={"file": ("lotes.xlsx", exported)},
        data={"mode": "upsert", "reason": "Prueba ida y vuelta"},
    )
    assert result.status_code == 200, result.text
    assert not result.json()["errors"], result.json()
    create(
        c,
        "/api/catalogs/import/execute",
        {"token": result.json()["token"], "confirmation": "IMPORTAR"},
    )
    legacy = (
        "ID,Código,Descripción,Precio,Moneda,Estado\n"
        + f"{lot['id']},ROUNDTRIP,Descripción nueva,10,HNL,Disponible\n"
    )
    response = c.post(
        f"/api/entities/{e['id']}/catalogs/lots/import/preview",
        files={"file": ("lotes.csv", legacy.encode("utf-8"))},
        data={"mode": "upsert", "reason": "Archivo anterior"},
    )
    assert response.status_code == 200, response.text
    assert not response.json()["errors"], response.json()
    create(
        c,
        "/api/catalogs/import/execute",
        {"token": response.json()["token"], "confirmation": "IMPORTAR"},
    )
    items = c.get(f"/api/entities/{e['id']}/lots?q=ROUNDTRIP").json()["items"]
    assert Decimal(items[0]["area_m2"]) == Decimal("116.25")
    assert items[0]["pricing_unit"] == "m2"
    assert items[0]["quotation"]["price"] == 11625000


def test_plan_owner_from_contract_and_fixed_title(portfolio):
    c, e, customer, lot, contract = portfolio
    owner = c.get(f"/api/lots/{lot['id']}/plan-owner").json()
    assert owner["contract"]["client_id"] == customer["id"]
    plan = create(
        c,
        f"/api/entities/{e['id']}/plans",
        rectangle(lot_id=lot["id"], owner="Nombre falsificado", title="Título modificado"),
    )
    payload = c.get(f"/api/plans/{plan['id']}").json()["payload"]
    assert payload["owner"] == customer["name"]
    assert payload["lot_label"] == lot["code"]
    assert payload["title"] == "PLANO DE REUNIÓN DE LOTES DE TERRENO"
    assert c.post(f"/api/entities/{e['id']}/plans", json=rectangle()).status_code == 422


def union_sources(c, e, customer, lot, offset=13):
    second = create(c, f"/api/entities/{e['id']}/lots", {"code": "LOTE-REUNIR", "price": "1"})
    first_data = rectangle(
        lot_id=lot["id"],
        vertices=[{"x": 0, "y": 0}, {"x": 13, "y": 0}, {"x": 13, "y": 13.75}, {"x": 0, "y": 13.75}],
    )
    second_data = rectangle(
        lot_id=second["id"],
        client_id=customer["id"],
        vertices=[
            {"x": offset, "y": 0},
            {"x": offset + 13, "y": 0},
            {"x": offset + 13, "y": 13.75},
            {"x": offset, "y": 13.75},
        ],
    )
    a = create(c, f"/api/entities/{e['id']}/plans", first_data)
    b = create(c, f"/api/entities/{e['id']}/plans", second_data)
    return a, b


def test_reunion_contiguous_lots_no_contract_changes(portfolio):
    c, e, customer, lot, contract = portfolio
    a, b = union_sources(c, e, customer, lot)
    body = rectangle(lot_id=lot["id"], source_plan_ids=[a["id"], b["id"]])
    result = create(c, f"/api/entities/{e['id']}/plans/union", body)
    assert result["geometry"]["area_m2"] == 357.5
    assert len(result["geometry"]["points"]) == 4
    merged = create(c, f"/api/entities/{e['id']}/plans", result["payload"])
    payload = c.get(f"/api/plans/{merged['id']}").json()["payload"]
    assert payload["lot_label"] == lot["code"] + " / LOTE-REUNIR"
    assert payload["owner"] == customer["name"]
    assert c.get(f"/api/contracts/{contract['id']}").json()["price"] == contract["price"]
    assert c.get(f"/api/entities/{e['id']}/contracts").json()["total"] == 1


@pytest.mark.parametrize("offset", [12, 14])
def test_reunion_rejects_overlaps_and_separated_lots(portfolio, offset):
    c, e, customer, lot, _ = portfolio
    a, b = union_sources(c, e, customer, lot, offset)
    result = c.post(
        f"/api/entities/{e['id']}/plans/union",
        json=rectangle(lot_id=lot["id"], source_plan_ids=[a["id"], b["id"]]),
    )
    assert result.status_code == 422, result.text
