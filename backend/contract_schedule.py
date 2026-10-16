"""Amend schedules in place, preserving obligation IDs and paid applications."""

import json

from .finance import monthly_due, require


def update_schedule(db, contract, data, price, down, obligations):
    identifier = contract["id"]
    active = [o for o in obligations if not o["retired"]]
    prima = next(o for o in active if o["number"] == 0)
    monthly = [o for o in active if o["number"] > 0]
    retired_ids = []
    # Old versions appended a complete replacement block and left zero-valued
    # placeholders. Keep the real paid rows and the active pending rows.
    if len(monthly) > contract["installments"]:
        capacities = {}
        for version in db.execute(
            "SELECT snapshot FROM contract_versions WHERE contract_id=? ORDER BY version",
            (identifier,),
        ):
            for historical in json.loads(version["snapshot"]).get("obligations", []):
                if historical["amount"] > 0:
                    capacities.setdefault(historical["id"], historical["amount"])
        for o in monthly:
            if o["paid"] > 0 and o["amount"] == o["paid"]:
                o["amount"] = max(o["amount"], capacities.get(o["id"], o["amount"]))
        placeholders = [o for o in monthly if o["amount"] == o["paid"] == 0]
        retired_ids.extend(o["id"] for o in placeholders)
        monthly = [o for o in monthly if o not in placeholders]
    trailing = monthly[data.installments :]
    require(
        not any(o["paid"] for o in trailing),
        "No se puede reducir el número total de cuotas por debajo de cuotas con pagos. Mantenga esas cuotas en el plan",
        409,
    )
    retired_ids.extend(o["id"] for o in trailing)
    selected = monthly[: data.installments]
    for oid in retired_ids:
        db.execute("UPDATE obligations SET retired=1,amount=0,number=-id WHERE id=?", (oid,))
    # Temporary unique numbers allow the surviving rows to be renumbered after
    # compacting legacy placeholders; references to their IDs never change.
    for o in selected:
        db.execute("UPDATE obligations SET number=-id WHERE id=?", (o["id"],))
    while len(selected) < data.installments:
        oid = db.execute(
            "INSERT INTO obligations(contract_id,number,due_date,amount) VALUES(?,?,?,0)",
            (identifier, len(selected) + 1, str(data.first_due)),
        ).lastrowid
        selected.append({"id": oid, "paid": 0, "amount": 0})
    complete = [i for i, o in enumerate(selected) if o["paid"] > 0 and o["paid"] == o["amount"]]
    values = {i: selected[i]["paid"] for i in complete}
    budget = price - down - sum(values.values())
    free = [i for i in range(len(selected)) if i not in complete]
    require(
        budget >= sum(selected[i]["paid"] for i in free),
        "El precio no cubre lo pagado en las cuotas",
        409,
    )
    require(
        free or budget == 0,
        "Todas las cuotas están pagadas. Aumente el número total de cuotas para financiar un saldo adicional",
        409,
    )
    while free:
        base, remainder = divmod(budget, len(free))
        above = [i for i in free if selected[i]["paid"] > base]
        if not above:
            for position, i in enumerate(free):
                values[i] = base + (remainder if position == len(free) - 1 else 0)
            break
        for i in above:
            values[i] = selected[i]["paid"]
            budget -= values[i]
            free.remove(i)
    db.execute(
        "UPDATE obligations SET amount=?,due_date=? WHERE id=?",
        (down, str(data.down_due), prima["id"]),
    )
    for i, o in enumerate(selected):
        db.execute(
            "UPDATE obligations SET number=?,due_date=?,amount=?,retired=0 WHERE id=?",
            (i + 1, monthly_due(data.first_due, i).isoformat(), values[i], o["id"]),
        )
    return retired_ids
