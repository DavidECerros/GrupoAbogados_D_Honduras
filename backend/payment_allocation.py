"""Deterministic allocation and durable month labels for payments and exports."""

import hashlib
import json
from decimal import Decimal

from .db import setting
from .finance import authorize, balance, cents, require, row

MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def obligation_label(number, due_date):
    year, month = due_date[:7].split("-")
    return ("Prima" if number == 0 else f"Cuota {number}") + f" - {MONTHS[int(month) - 1]} {year}"


def plan_payment(db, user, data):
    contract = row(db, "contracts", data.contract_id)
    require(contract["status"] == "active", "El contrato está anulado; no admite cobros", 409)
    authorize(db, user, contract["entity_id"], True)
    received, applied, rate = cents(data.amount), cents(data.amount), None
    if data.currency != contract["currency"]:
        rate = setting(db, "exchange_rate")
        require(rate and Decimal(rate) > 0, "El superusuario debe configurar la tasa HNL por USD")
        applied = cents(
            data.amount / Decimal(rate) if data.currency == "HNL" else data.amount * Decimal(rate)
        )
    require(applied > 0, "El importe convertido es menor que un centavo")
    outstanding = balance(db, contract["id"])
    require(applied <= outstanding, "El pago excede el saldo pendiente", 409)
    pending = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM obligations WHERE contract_id=? AND paid<amount ORDER BY CASE WHEN number=0 THEN 0 ELSE 1 END,due_date,number",
            (contract["id"],),
        )
    ]
    first = 0
    if data.start_obligation_id is not None:
        first = next(
            (i for i, o in enumerate(pending) if o["id"] == data.start_obligation_id), None
        )
        require(
            first is not None,
            "La cuota seleccionada no pertenece al contrato o ya fue pagada. Actualice el estado de cuenta",
            409,
        )
    prior_pending = sum(o["amount"] - o["paid"] for o in pending[:first])
    require(
        applied <= sum(o["amount"] - o["paid"] for o in pending[first:]),
        "El importe excede el saldo del mes seleccionado y los siguientes. Seleccione una cuota anterior o aplicación automática",
        409,
    )
    allocations, remaining = [], applied
    for o in pending[first:]:
        if remaining == 0:
            break
        portion = min(remaining, o["amount"] - o["paid"])
        allocations.append(
            {
                "obligation_id": o["id"],
                "number": o["number"],
                "due_date": o["due_date"],
                "label": obligation_label(o["number"], o["due_date"]),
                "amount": portion,
                "remaining_after": o["amount"] - o["paid"] - portion,
            }
        )
        remaining -= portion
    require(remaining == 0, "No fue posible aplicar el pago", 409)
    result = {
        "received": received,
        "received_currency": data.currency,
        "applied": applied,
        "contract_currency": contract["currency"],
        "rate": rate,
        "balance_before": outstanding,
        "balance_after": outstanding - applied,
        "prior_pending": prior_pending,
        "allocations": allocations,
    }
    result["allocation_token"] = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()
    require(
        data.allocation_token is None or data.allocation_token == result["allocation_token"],
        "Las cuotas o el saldo cambiaron. Actualice la vista previa antes de confirmar el cobro",
        409,
    )
    return result


def allocation_map(db, payment_ids):
    ids = list(dict.fromkeys(payment_ids))
    result = {}
    for start in range(0, len(ids), 400):
        chunk = ids[start : start + 400]
        marks = ",".join("?" for _ in chunk)
        for receipt in db.execute(
            f"SELECT payment_id,snapshot FROM receipts WHERE payment_id IN ({marks})", chunk
        ):
            snap = json.loads(receipt["snapshot"])
            if "allocations" in snap:
                result[receipt["payment_id"]] = snap["allocations"]
        missing = [p for p in chunk if p not in result]
        if missing:
            marks = ",".join("?" for _ in missing)
            for item in db.execute(
                "SELECT a.payment_id,a.obligation_id,a.amount,o.number,o.due_date FROM allocations a JOIN obligations o ON o.id=a.obligation_id "
                f"WHERE a.payment_id IN ({marks}) ORDER BY a.payment_id,o.number",
                missing,
            ):
                detail = dict(item)
                detail.pop("payment_id")
                detail["label"] = obligation_label(detail["number"], detail["due_date"])
                detail["remaining_after"] = None
                result.setdefault(item["payment_id"], []).append(detail)
    return result


def allocation_text(details, currency):
    return "; ".join(
        f"{d['label']}: {currency} {d['amount'] / 100:,.2f}"
        + (" (abono parcial)" if d.get("remaining_after") else "")
        for d in details
    )


def freeze_allocations(db, contract):
    receipts = list(
        db.execute(
            "SELECT r.* FROM receipts r JOIN payments p ON p.id=r.payment_id WHERE p.contract_id=?",
            (contract,),
        )
    )
    details = allocation_map(db, [r["payment_id"] for r in receipts])
    for r in receipts:
        snap = json.loads(r["snapshot"])
        if "allocations" not in snap:
            snap["allocations"] = details.get(r["payment_id"], [])
            db.execute(
                "UPDATE receipts SET snapshot=? WHERE id=?",
                (json.dumps(snap, ensure_ascii=False), r["id"]),
            )
