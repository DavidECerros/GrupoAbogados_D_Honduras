import calendar
import hashlib
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

from .db import audit, now, setting, today


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def require(condition, message, status=422):
    if not condition:
        raise HTTPException(status, message)


def row(db, table, identifier):
    # Table names are constants supplied by server code, never request values.
    found = db.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
    require(found is not None, "Registro no encontrado", 404)
    return dict(found)


def authorize(db, user, entity, write=False):
    ent = row(db, "entities", entity)
    require(
        user["role"] == "superuser"
        or db.execute(
            "SELECT 1 FROM user_entities WHERE user_id=? AND entity_id=?", (user["id"], entity)
        ).fetchone(),
        "Entidad no autorizada",
        403,
    )
    if write:
        require(ent["status"] == "active", "La lotificadora está archivada", 409)
    return ent


def admin(user):
    require(user["role"] == "superuser", "Se requiere superusuario", 403)


def schedule(db, contract, price, down, count, down_due, first_due):
    require(down <= price, "La prima no puede exceder el precio")
    db.execute(
        "INSERT INTO obligations(contract_id,number,due_date,amount) VALUES(?,?,?,?)",
        (contract, 0, str(down_due), down),
    )
    base = (price - down) // count
    for index in range(count):
        month_index = first_due.year * 12 + first_due.month - 1 + index
        year, month = divmod(month_index, 12)
        month += 1
        due = date(year, month, min(first_due.day, calendar.monthrange(year, month)[1]))
        amount = base if index < count - 1 else price - down - base * (count - 1)
        db.execute(
            "INSERT INTO obligations(contract_id,number,due_date,amount) VALUES(?,?,?,?)",
            (contract, index + 1, due.isoformat(), amount),
        )


def create_sale(db, user, entity, data):
    authorize(db, user, entity, True)
    lot, client = row(db, "lots", data.lot_id), row(db, "clients", data.client_id)
    require(
        lot["entity_id"] == entity and client["entity_id"] == entity,
        "Registros de otra entidad",
        403,
    )
    require(
        lot["currency"] == data.currency, "La moneda contractual debe coincidir con la del lote"
    )
    require(lot["status"] != "sold", "Lote vendido", 409)
    if lot["status"] == "reserved":
        reservation = db.execute(
            "SELECT * FROM reservations WHERE lot_id=? AND status='active'", (lot["id"],)
        ).fetchone()
        require(
            reservation and reservation["client_id"] == client["id"], "Reserva de otro cliente", 409
        )
        require(
            reservation["expires_on"] >= today(db).isoformat(),
            "Reserva vencida: requiere revisión",
            409,
        )
        db.execute("UPDATE reservations SET status='converted' WHERE id=?", (reservation["id"],))
    price, down = cents(data.price), cents(data.down_payment)
    require(down <= price, "Prima mayor que el precio")
    identifier = db.execute(
        "INSERT INTO contracts(entity_id,lot_id,client_id,price,currency,down_payment,installments,down_due,first_due,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            entity,
            lot["id"],
            client["id"],
            price,
            data.currency,
            down,
            data.installments,
            str(data.down_due),
            str(data.first_due),
            user["id"],
            now(),
        ),
    ).lastrowid
    schedule(db, identifier, price, down, data.installments, data.down_due, data.first_due)
    db.execute("UPDATE lots SET status='sold' WHERE id=?", (lot["id"],))
    result = row(db, "contracts", identifier)
    audit(db, user, "create_sale", entity, "contract", identifier, after=result)
    return result


def balance(db, contract):
    return db.execute(
        "SELECT COALESCE(SUM(amount-paid),0) FROM obligations WHERE contract_id=?", (contract,)
    ).fetchone()[0]


def statement(db, user, identifier):
    contract = row(db, "contracts", identifier)
    authorize(db, user, contract["entity_id"])
    obligations = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM obligations WHERE contract_id=? ORDER BY number", (identifier,)
        )
    ]
    # Account statement is permitted for collection; payment operator identity stays private.
    payments = [
        dict(r)
        for r in db.execute(
            "SELECT p.id,p.payment_date,p.received,p.received_currency,p.applied,p.rate,p.status,r.folio FROM payments p JOIN receipts r ON r.payment_id=p.id WHERE p.contract_id=? ORDER BY p.id",
            (identifier,),
        )
    ]
    return {
        **contract,
        "client": row(db, "clients", contract["client_id"]),
        "lot": row(db, "lots", contract["lot_id"]),
        "balance": balance(db, identifier),
        "obligations": obligations,
        "payments": payments,
        "transfers": [
            dict(r)
            for r in db.execute(
                "SELECT previous_client,new_client,effective_date,reason,balance FROM transfers WHERE contract_id=? ORDER BY id",
                (identifier,),
            )
        ],
    }


def create_payment(db, user, data):
    contract = row(db, "contracts", data.contract_id)
    entity = authorize(db, user, contract["entity_id"], True)
    canonical = data.model_dump(mode="json")
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    previous = db.execute(
        "SELECT * FROM payments WHERE operation_id=?", (data.operation_id,)
    ).fetchone()
    if previous:
        require(
            previous["request_hash"] == fingerprint and previous["created_by"] == user["id"],
            "Identificador de operación ya utilizado",
            409,
        )
        return payment_result(db, previous["id"])
    received, applied, rate = cents(data.amount), cents(data.amount), None
    if data.currency != contract["currency"]:
        rate = setting(db, "exchange_rate")
        require(rate and Decimal(rate) > 0, "El superusuario debe configurar la tasa HNL por USD")
        amount = (
            data.amount / Decimal(rate) if data.currency == "HNL" else data.amount * Decimal(rate)
        )
        applied = cents(amount)
    require(applied > 0, "El importe convertido es menor que un centavo")
    before_balance = balance(db, contract["id"])
    require(applied <= before_balance, "El pago excede el saldo pendiente", 409)
    require(data.method == "cash" or data.bank_reference, "Se requiere comprobante bancario")
    payment_date = data.payment_date or today(db)
    require(payment_date <= today(db), "No se aceptan fechas de pago futuras")
    identifier = db.execute(
        "INSERT INTO payments(entity_id,contract_id,client_id,operation_id,request_hash,payment_date,received,received_currency,applied,rate,method,bank_reference,notes,created_by,created_at,balance_after) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            entity["id"],
            contract["id"],
            contract["client_id"],
            data.operation_id,
            fingerprint,
            str(payment_date),
            received,
            data.currency,
            applied,
            rate,
            data.method,
            data.bank_reference,
            data.notes,
            user["id"],
            now(),
            before_balance - applied,
        ),
    ).lastrowid
    remaining = applied
    for obligation in db.execute(
        "SELECT * FROM obligations WHERE contract_id=? AND paid<amount ORDER BY CASE WHEN number=0 THEN 0 ELSE 1 END,due_date,number",
        (contract["id"],),
    ).fetchall():
        portion = min(remaining, obligation["amount"] - obligation["paid"])
        if not portion:
            break
        db.execute("UPDATE obligations SET paid=paid+? WHERE id=?", (portion, obligation["id"]))
        db.execute("INSERT INTO allocations VALUES(?,?,?)", (identifier, obligation["id"], portion))
        remaining -= portion
    require(remaining == 0, "No fue posible aplicar el pago", 409)
    issued = today(db)
    db.execute(
        "INSERT INTO receipt_sequences VALUES(?,?,1) ON CONFLICT(entity_id,year) DO UPDATE SET number=number+1",
        (entity["id"], issued.year),
    )
    number = db.execute(
        "SELECT number FROM receipt_sequences WHERE entity_id=? AND year=?",
        (entity["id"], issued.year),
    ).fetchone()[0]
    folio = f"REC-{issued.year}-{number:05d}"
    snapshot = {
        "entity": entity["name"],
        "entity_id": entity["id"],
        "logo": entity["logo"],
        "client": row(db, "clients", contract["client_id"])["name"],
        "lot": row(db, "lots", contract["lot_id"])["code"],
        "folio": folio,
        "payment_date": str(payment_date),
        "issued_date": str(issued),
        "received": received,
        "received_currency": data.currency,
        "applied": applied,
        "contract_currency": contract["currency"],
        "rate": rate,
        "method": data.method,
        "bank_reference": data.bank_reference,
        "operator": user["full_name"],
        "balance_after": before_balance - applied,
    }
    db.execute(
        "INSERT INTO receipts(payment_id,entity_id,year,number,folio,snapshot) VALUES(?,?,?,?,?,?)",
        (
            identifier,
            entity["id"],
            issued.year,
            number,
            folio,
            json.dumps(snapshot, ensure_ascii=False),
        ),
    )
    audit(
        db,
        user,
        "create_payment",
        entity["id"],
        "payment",
        identifier,
        after={
            "received": received,
            "currency": data.currency,
            "applied": applied,
            "balance": before_balance - applied,
            "folio": folio,
        },
    )
    return payment_result(db, identifier)


def payment_result(db, identifier):
    return dict(
        db.execute(
            "SELECT p.*,r.id receipt_id,r.folio,r.status receipt_status FROM payments p JOIN receipts r ON r.payment_id=p.id WHERE p.id=?",
            (identifier,),
        ).fetchone()
    )


def void_payment(db, user, identifier, reason):
    admin(user)
    payment = row(db, "payments", identifier)
    authorize(db, user, payment["entity_id"])
    require(payment["status"] == "valid", "Pago ya anulado", 409)
    for allocation in db.execute(
        "SELECT * FROM allocations WHERE payment_id=?", (identifier,)
    ).fetchall():
        db.execute(
            "UPDATE obligations SET paid=paid-? WHERE id=?",
            (allocation["amount"], allocation["obligation_id"]),
        )
    db.execute(
        "UPDATE payments SET status='void',void_by=?,void_reason=?,void_at=? WHERE id=?",
        (user["id"], reason, now(), identifier),
    )
    db.execute("UPDATE receipts SET status='void',path=NULL WHERE payment_id=?", (identifier,))
    audit(
        db,
        user,
        "void_payment",
        payment["entity_id"],
        "payment",
        identifier,
        reason,
        before=payment,
        after={"status": "void"},
    )


def release_reservation(db, user, identifier, reason):
    admin(user)
    reservation = row(db, "reservations", identifier)
    authorize(db, user, reservation["entity_id"])
    require(reservation["status"] == "active", "Reserva ya resuelta", 409)
    db.execute("UPDATE reservations SET status='released' WHERE id=?", (identifier,))
    db.execute("UPDATE lots SET status='available' WHERE id=?", (reservation["lot_id"],))
    audit(
        db, user, "release_reservation", reservation["entity_id"], "reservation", identifier, reason
    )


def transfer_contract(db, user, identifier, data):
    admin(user)
    contract = row(db, "contracts", identifier)
    authorize(db, user, contract["entity_id"], True)
    client = row(db, "clients", data.new_client_id)
    require(client["entity_id"] == contract["entity_id"], "Cliente de otra entidad", 403)
    require(client["id"] != contract["client_id"], "El nuevo propietario debe ser diferente")
    require(
        data.effective_date == today(db),
        "La cesión debe ser efectiva hoy; no se reescriben propietarios de pagos anteriores",
    )
    transferred_balance = balance(db, identifier)
    db.execute(
        "INSERT INTO transfers(contract_id,previous_client,new_client,effective_date,reason,balance,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            identifier,
            contract["client_id"],
            client["id"],
            str(data.effective_date),
            data.reason,
            transferred_balance,
            user["id"],
            now(),
        ),
    )
    db.execute(
        "INSERT INTO contract_versions(contract_id,version,snapshot,reason,created_by,created_at) VALUES(?,?,?,?,?,?)",
        (identifier, contract["version"], json.dumps(contract), data.reason, user["id"], now()),
    )
    db.execute(
        "UPDATE contracts SET client_id=?,version=version+1 WHERE id=?", (client["id"], identifier)
    )
    audit(
        db,
        user,
        "transfer_contract",
        contract["entity_id"],
        "contract",
        identifier,
        data.reason,
        before=contract,
        after={"client_id": client["id"], "balance": transferred_balance},
    )


def amend_contract(db, user, identifier, data):
    admin(user)
    contract = row(db, "contracts", identifier)
    authorize(db, user, contract["entity_id"], True)
    # Existing applications must remain intact. Until a re-amortization model is agreed,
    # only contracts without any payment history may have financial terms changed.
    require(
        not db.execute("SELECT 1 FROM payments WHERE contract_id=?", (identifier,)).fetchone(),
        "Un contrato con historial de pagos conserva sus condiciones financieras",
        409,
    )
    price, down = cents(data.price), cents(data.down_payment)
    require(down <= price, "Prima mayor que el precio")
    db.execute(
        "INSERT INTO contract_versions(contract_id,version,snapshot,reason,created_by,created_at) VALUES(?,?,?,?,?,?)",
        (identifier, contract["version"], json.dumps(contract), data.reason, user["id"], now()),
    )
    db.execute("DELETE FROM obligations WHERE contract_id=?", (identifier,))
    schedule(db, identifier, price, down, data.installments, data.down_due, data.first_due)
    db.execute(
        "UPDATE contracts SET price=?,down_payment=?,installments=?,down_due=?,first_due=?,version=version+1 WHERE id=?",
        (price, down, data.installments, str(data.down_due), str(data.first_due), identifier),
    )
    audit(
        db,
        user,
        "amend_contract",
        contract["entity_id"],
        "contract",
        identifier,
        data.reason,
        before=contract,
        after=row(db, "contracts", identifier),
    )


def arrears(db, entity=None, client=None, due_from=None, due_to=None):
    current = today(db)
    sql = """SELECT c.id contract_id,c.entity_id,e.name entity,c.client_id,cl.name client,l.code lot,c.currency,
    SUM(o.amount-o.paid) balance,
    COALESCE(SUM(CASE WHEN o.due_date<? THEN o.amount-o.paid ELSE 0 END),0) overdue,
    MIN(CASE WHEN o.amount>o.paid THEN o.due_date END) oldest_due
    FROM contracts c JOIN entities e ON e.id=c.entity_id JOIN clients cl ON cl.id=c.client_id
    JOIN lots l ON l.id=c.lot_id JOIN obligations o ON o.contract_id=c.id WHERE c.status='active' """
    args = [str(current)]
    if entity:
        sql += " AND c.entity_id=?"
        args.append(entity)
    if client:
        sql += " AND c.client_id=?"
        args.append(client)
    sql += " GROUP BY c.id"
    results = []
    for r in db.execute(sql, args):
        item = dict(r)
        due = date.fromisoformat(item["oldest_due"]) if item["oldest_due"] else None
        if due_from and (not due or due < due_from):
            continue
        if due_to and (not due or due > due_to):
            continue
        days = max(0, (current - due).days) if due else 0
        item.update(
            days_late=days,
            color="red" if days else "yellow" if due and (due - current).days <= 4 else "green",
            category="moroso"
            if days > 30
            else "vencido"
            if days
            else "próximo"
            if due and (due - current).days <= 4
            else "al día",
        )
        results.append(item)
    return sorted(results, key=lambda x: (-x["days_late"], -x["overdue"]))
