"""Business reporting with entity names, explicit currencies and decimal amounts."""

from decimal import Decimal

from .db import today
from .finance import commercial_status, require

STATES = {
    "active": "Activo",
    "archived": "Archivada",
    "inactive": "Inhabilitado",
    "available": "Disponible",
    "reserved": "Reservado",
    "sold": "Vendido",
    "valid": "Confirmado",
    "void": "Anulado",
    "pending_payment": "Pendiente de cancelar",
    "paid": "Cancelado (pagado)",
    "pending_deed": "Pendiente de escriturar",
    "deeded": "Escriturado",
    "annulled": "Anulado",
    "released": "Liberada",
    "converted": "Convertida",
}


def amount(value):
    return Decimal(value or 0) / 100


def build_reports(db, entity, kind, since, until, state):
    require(
        kind in ("all", "contracts", "payments", "lots", "finances", "overdue"), "Reporte inválido"
    )
    cutoff = today(db).isoformat()
    start, end = str(since or ""), str(until or "")
    require(not start or not end or start <= end, "El rango de fechas es inválido")
    allowed_states = {
        "all": (),
        "lots": ("available", "reserved", "sold", "deleted"),
        "contracts": ("pending_payment", "paid", "pending_deed", "deeded", "annulled"),
        "payments": ("valid", "void"),
        "finances": (),
        "overdue": (),
    }
    require(not state or state in allowed_states[kind], "Estado no válido para este reporte")
    entities = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM entities" + (" WHERE id=?" if entity else "") + " ORDER BY name",
            [entity] if entity else [],
        )
    ]
    names = {r["id"]: r["name"] for r in entities}

    def selected(table):
        return [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM {table}"
                + (" WHERE entity_id=?" if entity else "")
                + " ORDER BY id",
                [entity] if entity else [],
            )
        ]

    clients, lots, contracts, payments = [
        selected(t) for t in ("clients", "lots", "contracts", "payments")
    ]
    from .payment_allocation import allocation_map, allocation_text

    payment_details = allocation_map(db, [p["id"] for p in payments])
    client_names = {r["id"]: r["name"] for r in clients}
    lot_codes = {r["id"]: r["code"] for r in lots}
    obligations = [
        dict(r)
        for r in db.execute(
            "SELECT o.* FROM obligations o JOIN contracts c ON c.id=o.contract_id WHERE o.retired=0"
            + (" AND c.entity_id=?" if entity else "")
            + " ORDER BY o.contract_id,o.number",
            [entity] if entity else [],
        )
    ]
    by_contract = {}
    for o in obligations:
        by_contract.setdefault(o["contract_id"], []).append(o)
    contract_map = {c["id"]: c for c in contracts}
    for c in contracts:
        c["balance"] = sum(o["amount"] - o["paid"] for o in by_contract.get(c["id"], []))
        c["commercial_status"] = commercial_status(c, c["balance"])

    def period(d):
        return (not start or d[:10] >= start) and (not end or d[:10] <= end)

    tables = {
        "Información": [
            {
                "Fecha de corte": cutoff,
                "Lotificadora": names.get(entity, "Todas"),
                "Desde": start or "Sin límite",
                "Hasta": end or "Sin límite",
                "Reporte": kind,
                "Filtro de estado": STATES.get(state, state) or "Todos",
                "Criterio": "Fechas: creación de contratos, fecha de pago en cobros/finanzas y vencimiento en mora. Saldos y estados actuales a la fecha de corte. Lotes sin filtro de fecha. Importes en unidades monetarias, separados por moneda. Finanzas resume ventas, cartera y cobros; no calcula utilidad ni gastos.",
            }
        ]
    }
    if kind in ("all", "contracts"):
        tables["Contratos"] = [
            {
                "ID": c["id"],
                "Lotificadora": names[c["entity_id"]],
                "Cliente": client_names[c["client_id"]],
                "Lote": lot_codes[c["lot_id"]],
                "Moneda": c["currency"],
                "Precio": amount(c["price"]),
                "Prima": amount(c["down_payment"]),
                "A financiar original": amount(c["price"] - c["down_payment"]),
                "Saldo actual": amount(c["balance"]),
                "Estado": STATES[c["commercial_status"]],
                "Creado": c["created_at"][:10],
                "Versión": c["version"],
            }
            for c in contracts
            if period(c["created_at"]) and (not state or c["commercial_status"] == state)
        ]
    if kind in ("all", "lots"):
        from fastapi import HTTPException

        from .land_pricing import quote

        for lot in lots:
            try:
                lot["quote"] = quote(db, lot)
                lot["quote_error"] = ""
            except HTTPException as exc:
                lot["quote"] = {}
                lot["quote_error"] = exc.detail
        tables["Lotes"] = [
            {
                "ID": lot["id"],
                "Lotificadora": names[lot["entity_id"]],
                "Código": lot["code"],
                "Ubicación": lot["description"],
                "Área m²": Decimal(lot["area_m2"]),
                "Moneda precio fijo": lot["currency"],
                "Precio fijo registrado": amount(lot["price"])
                if lot["pricing_unit"] == "fixed"
                else None,
                "Modo de precio": lot["pricing_unit"],
                "Valor de nueva venta": amount(lot["quote"]["price"]) if lot["quote"] else None,
                "Moneda de nueva venta": lot["quote"].get("currency", ""),
                "Observación de tarifa": lot["quote_error"],
                "Estado": STATES[lot["status"]],
                "Eliminado": "Sí" if lot["deleted_at"] else "No",
            }
            for lot in lots
            if not state
            or (
                lot["deleted_at"]
                if state == "deleted"
                else not lot["deleted_at"] and lot["status"] == state
            )
        ]
    if kind in ("all", "payments", "finances"):
        folios = {
            r["payment_id"]: r["folio"] for r in db.execute("SELECT payment_id,folio FROM receipts")
        }
        tables["Cobros"] = [
            {
                "ID": p["id"],
                "Lotificadora": names[p["entity_id"]],
                "Contrato": p["contract_id"],
                "Cliente": client_names[p["client_id"]],
                "Lote": lot_codes[contract_map[p["contract_id"]]["lot_id"]],
                "Fecha": p["payment_date"],
                "Folio": folios.get(p["id"], ""),
                "Moneda recibida": p["received_currency"],
                "Recibido": amount(p["received"]),
                "Moneda contrato": contract_map[p["contract_id"]]["currency"],
                "Aplicado": amount(p["applied"]),
                "Tasa HNL por USD": p["rate"],
                "Método": p["method"],
                "Referencia": p["bank_reference"],
                "Estado": STATES[p["status"]],
                "Meses / cuotas pagados": allocation_text(
                    payment_details.get(p["id"], []), contract_map[p["contract_id"]]["currency"]
                ),
            }
            for p in payments
            if period(p["payment_date"]) and (not state or p["status"] == state)
        ]
        tables["Aplicaciones por mes"] = [
            {
                "Pago": p["id"],
                "Folio": folios.get(p["id"], ""),
                "Lotificadora": names[p["entity_id"]],
                "Contrato": p["contract_id"],
                "Cliente": client_names[p["client_id"]],
                "Lote": lot_codes[contract_map[p["contract_id"]]["lot_id"]],
                "Fecha de pago": p["payment_date"],
                "Mes / cuota": d["label"],
                "Vencimiento": d["due_date"],
                "Moneda": contract_map[p["contract_id"]]["currency"],
                "Aplicado": amount(d["amount"]),
                "Estado cobro": STATES[p["status"]],
            }
            for p in payments
            if period(p["payment_date"]) and (not state or p["status"] == state)
            for d in payment_details.get(p["id"], [])
        ]
    if kind in ("all", "overdue"):
        tables["Cobros vencidos"] = [
            {
                "Lotificadora": names[c["entity_id"]],
                "Contrato": c["id"],
                "Cliente": client_names[c["client_id"]],
                "Lote": lot_codes[c["lot_id"]],
                "Moneda": c["currency"],
                "Obligación": "Prima" if o["number"] == 0 else f"Cuota {o['number']}",
                "Vencimiento": o["due_date"],
                "Importe": amount(o["amount"]),
                "Pagado": amount(o["paid"]),
                "Pendiente vencido": amount(o["amount"] - o["paid"]),
            }
            for c in contracts
            if c["status"] == "active"
            for o in by_contract.get(c["id"], [])
            if o["due_date"] < cutoff and o["amount"] > o["paid"] and period(o["due_date"])
        ]
    if kind in ("all", "finances"):
        financial = []
        for e in entities:
            for currency in ("HNL", "USD"):
                paid = [
                    p
                    for p in payments
                    if p["entity_id"] == e["id"]
                    and p["received_currency"] == currency
                    and period(p["payment_date"])
                ]
                current = [
                    c
                    for c in contracts
                    if c["entity_id"] == e["id"]
                    and c["currency"] == currency
                    and c["status"] == "active"
                ]
                financial.append(
                    {
                        "Lotificadora": e["name"],
                        "Moneda": currency,
                        "Cobros registrados en período": amount(sum(p["received"] for p in paid)),
                        "Cobros anulados en período": amount(
                            sum(p["received"] for p in paid if p["status"] == "void")
                        ),
                        "Cobros netos en período": amount(
                            sum(p["received"] for p in paid if p["status"] == "valid")
                        ),
                        "Valor contratos activos creados en período": amount(
                            sum(c["price"] for c in current if period(c["created_at"]))
                        ),
                        "Cartera pendiente actual": amount(sum(c["balance"] for c in current)),
                        "Cartera vencida actual": amount(
                            sum(
                                o["amount"] - o["paid"]
                                for c in current
                                for o in by_contract.get(c["id"], [])
                                if o["due_date"] < cutoff
                            )
                        ),
                    }
                )
        tables["Finanzas"] = financial
    if kind == "all":
        tables["Lotificadoras"] = [
            {
                "ID": e["id"],
                "Nombre": e["name"],
                "Moneda": e["currency"],
                "Estado": STATES[e["status"]],
            }
            for e in entities
        ]
        tables["Clientes"] = [
            {
                "ID": c["id"],
                "Lotificadora": names[c["entity_id"]],
                "Nombre": c["name"],
                "Documento": c["document"],
                "Tipo": c["document_type"],
                "Teléfono": c["phone"],
                "Correo": c["email"],
                "Notas": c["notes"],
                "Estado": STATES[c["status"]],
                "Eliminado": "Sí" if c["deleted_at"] else "No",
            }
            for c in clients
        ]
        tables["Plan de cuotas"] = [
            {
                "Contrato": c["id"],
                "Lotificadora": names[c["entity_id"]],
                "Lote": lot_codes[c["lot_id"]],
                "Moneda": c["currency"],
                "Obligación": o["number"],
                "Vencimiento": o["due_date"],
                "Importe": amount(o["amount"]),
                "Pagado": amount(o["paid"]),
                "Pendiente": amount(o["amount"] - o["paid"]),
            }
            for c in contracts
            for o in by_contract.get(c["id"], [])
        ]
        tables["Reservas"] = [
            {
                "ID": r["id"],
                "Lotificadora": names[r["entity_id"]],
                "Cliente": client_names[r["client_id"]],
                "Lote": lot_codes[r["lot_id"]],
                "Vencimiento": r["expires_on"],
                "Estado": STATES[r["status"]],
                "Eliminada": "Sí" if r["deleted_at"] else "No",
            }
            for r in selected("reservations")
        ]
    return tables
