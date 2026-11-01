"""Deed records and optional selling terms for a lot, independent of contracts."""

import json
from decimal import Decimal

from . import models
from .finance import cents, require, row
from .land_pricing import areas

DEED_FIELDS = (
    "registered_client_id",
    "deed_client_name",
    "deed_client_document",
    "deed_client_phone",
    "deed_client_email",
    "deed_address",
    "boundaries",
)


def storage(db, entity, data, previous=None):
    values = {}
    if previous:
        values = {k: previous[k] for k in models.Lot.model_fields if k in previous}
        values["price"] = None if previous["pricing_pending"] else Decimal(previous["price"]) / 100
        values["boundaries"] = json.loads(previous["boundaries"])
    values.update(data.model_dump(exclude_unset=True))
    if data.area_v2 is not None and "area_m2" not in data.model_fields_set:
        values["area_m2"] = "0"
    model = models.Lot(**values)
    if model.registered_client_id:
        client = row(db, "clients", model.registered_client_id)
        require(client["entity_id"] == entity, "Cliente de otra lotificadora", 403)
        # Take a copy when first linking. Subsequent deed spelling edits remain independent.
        if not previous or previous["registered_client_id"] != model.registered_client_id:
            require(
                not client["deleted_at"], "Restaure el cliente antes de vincularlo al lote", 409
            )
            for field, source in (
                ("deed_client_name", "name"),
                ("deed_client_document", "document"),
                ("deed_client_phone", "phone"),
                ("deed_client_email", "email"),
            ):
                if not getattr(model, field) or field not in data.model_fields_set:
                    setattr(model, field, client[source])
    require(
        len({b.side.casefold() for b in model.boundaries}) == len(model.boundaries),
        "No repita la identificación del lado en las colindancias",
    )
    result = model.model_dump(mode="json")
    result.pop("area_v2")
    result["area_m2"] = areas(db, model)
    result["price"] = cents(model.price) if model.price is not None else 1
    result["pricing_pending"] = int(model.pricing_unit == "fixed" and model.price is None)
    result["boundaries"] = json.dumps(result["boundaries"], ensure_ascii=False)
    return result


def present(record):
    result = dict(record)
    if isinstance(result.get("boundaries"), str):
        result["boundaries"] = json.loads(result["boundaries"])
    # The legacy SQL positive-price constraint uses an internal sentinel for drafts.
    # It must never become a displayed price or an accepted selling quotation.
    if result.get("pricing_pending"):
        result["price"] = None
    return result
