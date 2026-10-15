"""Exact decimal areas and immutable pricing basis for new sales."""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from .db import setting
from .finance import cents, require


def entity_rates(db, entity):
    record = db.execute("SELECT * FROM entity_prices WHERE entity_id=?", (entity,)).fetchone()
    return (
        dict(record)
        if record
        else {
            "entity_id": entity,
            "price_m2": None,
            "price_v2": None,
            "currency": db.execute(
                "SELECT currency FROM entities WHERE id=?", (entity,)
            ).fetchone()[0],
            "updated_at": "",
        }
    )


def factor(db):
    return Decimal(setting(db, "vara_m2") or "0.697224")


def areas(db, data):
    m2 = data.area_m2
    if data.area_v2 is not None:
        converted = (data.area_v2 * factor(db)).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)
        require(
            not m2 or abs(m2 - converted) <= Decimal(".00001"),
            "Las áreas en m² y vara² no coinciden; ingrese una sola unidad",
        )
        m2 = converted
    require(
        data.pricing_unit == "fixed" or m2 > 0, "Registre el área del lote para calcular su valor"
    )
    return str(m2)


def quote(db, lot):
    rates = entity_rates(db, lot["entity_id"])
    unit = lot["pricing_unit"]
    area = Decimal(lot["area_m2"])
    result = {
        "lot_id": lot["id"],
        "unit": unit,
        "area_m2": str(area),
        "area_v2": str((area / factor(db)).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)),
        "vara_m2": str(factor(db)),
        "currency": lot["currency"],
        "price": lot["price"],
        "unit_price": None,
        "entity_id": lot["entity_id"],
    }
    if unit != "fixed":
        price = rates["price_" + unit]
        require(
            price and Decimal(price) > 0,
            "El superusuario debe registrar la tarifa de esta lotificadora por "
            + ("m²" if unit == "m2" else "vara²"),
            409,
        )
        require(area > 0, "El lote no tiene área registrada", 409)
        quantity = area if unit == "m2" else area / factor(db)
        result.update(
            currency=rates["currency"],
            price=cents(quantity * Decimal(price)),
            unit_price=price,
            rate_updated=rates["updated_at"],
        )
        require(0 < result["price"] <= 99999999999999, "Precio del lote fuera de rango")
    result["quote_token"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def describe(db, lot):
    result = dict(lot)
    result["area_v2"] = str(
        (Decimal(result["area_m2"]) / factor(db)).quantize(
            Decimal(".000001"), rounding=ROUND_HALF_UP
        )
    )
    try:
        result["quotation"] = quote(db, lot)
    except Exception as exc:
        from fastapi import HTTPException

        if not isinstance(exc, HTTPException):
            raise
        result["quotation_error"] = exc.detail
    return result
