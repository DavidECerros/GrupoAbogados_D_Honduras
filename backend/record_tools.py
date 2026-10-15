"""Reversible removal and audited corrections without breaking financial history."""

import json

from . import artifacts
from . import models as m
from .db import audit, now, today
from .finance import admin, authorize, release_reservation, require, row, void_payment

TABLES = {
    "clients": "clients",
    "lots": "lots",
    "reservations": "reservations",
    "plans": "land_plans",
    "contracts": "contracts",
    "users": "users",
    "payments": "payments",
    "entities": "entities",
    "approvals": "approvals",
}


def register(app, User, DB):
    @app.put("/api/contracts/{identifier}/closing-status")
    def closing_status(identifier: int, data: m.ContractClosing, user: User, db: DB):
        from .finance import balance

        admin(user)
        previous = row(db, "contracts", identifier)
        authorize(db, user, previous["entity_id"], True)
        require(previous["status"] == "active", "El contrato está anulado", 409)
        require(
            balance(db, identifier) == 0,
            "El contrato sigue pendiente de cancelar: registre los cobros antes de cambiar su estado de escrituración",
            409,
        )
        db.execute("UPDATE contracts SET closing_status=? WHERE id=?", (data.status, identifier))
        result = row(db, "contracts", identifier)
        audit(
            db,
            user,
            "update_contract_closing",
            previous["entity_id"],
            "contract",
            identifier,
            reason=data.reason,
            before=previous,
            after=result,
        )
        return result

    @app.put("/api/approvals/{identifier}")
    def edit_approval(identifier: int, data: m.Reason, user: User, db: DB):
        admin(user)
        previous = row(db, "approvals", identifier)
        authorize(db, user, previous["entity_id"])
        require(previous["status"] == "pending", "La solicitud ya fue resuelta", 409)
        db.execute("UPDATE approvals SET reason=? WHERE id=?", (data.reason, identifier))
        result = row(db, "approvals", identifier)
        audit(
            db,
            user,
            "update_approval_reason",
            previous["entity_id"],
            "approval",
            identifier,
            before=previous,
            after=result,
        )
        return result

    @app.post("/api/{kind}/{identifier}/lifecycle")
    def lifecycle(kind: str, identifier: int, data: m.Lifecycle, user: User, db: DB):
        admin(user)
        require(kind in TABLES, "Módulo no válido", 404)
        table = TABLES[kind]
        before = row(db, table, identifier)
        entity = identifier if kind == "entities" else before.get("entity_id")
        if entity:
            authorize(db, user, entity)
        if data.action == "purge":
            require(
                kind in ("lots", "clients"), "Solo se depuran lotes y clientes sin referencias", 422
            )
            require(
                before["deleted_at"], "Elimine primero el registro de la lista de vigentes", 409
            )
            references = (
                [("contracts", "lot_id"), ("reservations", "lot_id"), ("land_plans", "lot_id")]
                if kind == "lots"
                else [
                    ("contracts", "client_id"),
                    ("reservations", "client_id"),
                    ("payments", "client_id"),
                    ("transfers", "previous_client"),
                    ("transfers", "new_client"),
                ]
            )
            linked = [
                table
                for table, field in references
                if db.execute(
                    f"SELECT 1 FROM {table} WHERE {field}=? LIMIT 1", (identifier,)
                ).fetchone()
            ]
            if (
                kind == "clients"
                and db.execute(
                    "SELECT 1 FROM land_plans WHERE json_extract(payload,'$.client_id')=? LIMIT 1",
                    (identifier,),
                ).fetchone()
            ):
                linked.append("land_plans")
            require(
                not linked,
                "No se puede borrar definitivamente: tiene referencias en "
                + ", ".join(linked)
                + ". Restaure el registro y corrija sus datos; se conserva el historial",
                409,
            )
            db.commit()
            backup = artifacts.backup(user)
            db.execute("BEGIN IMMEDIATE")
            db.execute(f"DELETE FROM {TABLES[kind]} WHERE id=?", (identifier,))
            audit(
                db,
                user,
                "purge_" + kind,
                entity,
                kind,
                identifier,
                reason=data.reason,
                before=before,
            )
            return {"ok": True, "backup": backup.name}
        if kind == "users":
            require(before["role"] != "superuser", "El superusuario está protegido", 409)
            before = {
                k: v
                for k, v in before.items()
                if k not in ("password_hash", "failures", "locked_until")
            }
        if kind == "contracts" and data.action == "delete":
            require(before["status"] == "active", "El contrato ya está anulado", 409)
            require(
                not db.execute(
                    "SELECT 1 FROM payments WHERE contract_id=? AND status='valid'", (identifier,)
                ).fetchone(),
                "El contrato tiene cobros vigentes. Anule esos cobros antes de anular el contrato; no se eliminan cobros automáticamente",
                409,
            )
        if kind == "contracts" and data.action == "restore":
            require(before["status"] == "cancelled", "El contrato no está anulado", 409)
            lot = row(db, "lots", before["lot_id"])
            require(
                lot["status"] == "available" and not lot["deleted_at"],
                "El lote ya no está disponible; no se puede reactivar este contrato",
                409,
            )
            require(
                row(db, "clients", before["client_id"])["status"] == "active"
                and not row(db, "clients", before["client_id"])["deleted_at"],
                "Reactive primero el cliente",
                409,
            )
        if kind == "payments":
            require(
                data.action == "delete",
                "Un cobro anulado se corrige registrando un nuevo cobro; no se restaura",
                409,
            )
            require(before["status"] == "valid", "El pago ya está anulado", 409)
        if kind == "approvals":
            require(
                data.action == "delete" and before["status"] == "pending",
                "Solo se retiran solicitudes pendientes",
                409,
            )
        db.commit()
        backup = artifacts.backup(user)
        db.execute("BEGIN IMMEDIATE")
        removing = data.action == "delete"
        if kind == "entities":
            db.execute(
                "UPDATE entities SET status=? WHERE id=?",
                ("archived" if removing else "active", identifier),
            )
        elif kind == "approvals":
            db.execute(
                "UPDATE approvals SET status='rejected',resolved_by=?,resolved_at=?,resolution=? WHERE id=?",
                (user["id"], now(), data.reason, identifier),
            )
        elif kind == "users":
            db.execute("UPDATE users SET active=? WHERE id=?", (0 if removing else 1, identifier))
            db.execute("DELETE FROM sessions WHERE user_id=?", (identifier,))
        elif kind == "contracts":
            db.execute(
                "UPDATE contracts SET status=? WHERE id=?",
                ("cancelled" if removing else "active", identifier),
            )
            db.execute(
                "UPDATE lots SET status=? WHERE id=?",
                ("available" if removing else "sold", before["lot_id"]),
            )
            if removing:
                db.execute(
                    "UPDATE approvals SET status='rejected',resolved_by=?,resolved_at=?,resolution=? WHERE status='pending' AND action IN ('transfer_contract','amend_contract') AND record_id=?",
                    (user["id"], now(), "Contrato anulado: " + data.reason, identifier),
                )
        elif kind == "payments":
            void_payment(db, user, identifier, data.reason)
        else:
            if kind == "reservations" and removing and before["status"] == "active":
                release_reservation(db, user, identifier, data.reason)
            db.execute(
                f"UPDATE {table} SET deleted_at=? WHERE id=?",
                (now() if removing else None, identifier),
            )
            if kind == "clients":
                db.execute(
                    "UPDATE clients SET status=? WHERE id=?",
                    ("inactive" if removing else "active", identifier),
                )
        after = row(db, table, identifier)
        if kind == "users":
            after = {
                k: v
                for k, v in after.items()
                if k not in ("password_hash", "failures", "locked_until")
            }
        audit(
            db,
            user,
            "remove_" + kind if removing else "restore_" + kind,
            entity,
            kind,
            identifier,
            reason=data.reason,
            before=before,
            after=after,
        )
        return {"ok": True, "backup": backup.name, "record": after}

    @app.put("/api/reservations/{identifier}")
    def edit_reservation(identifier: int, data: m.Reservation, user: User, db: DB):
        admin(user)
        before = row(db, "reservations", identifier)
        authorize(db, user, before["entity_id"], True)
        require(
            before["status"] == "active" and not before["deleted_at"],
            "Solo se editan reservas activas; cree una nueva si fue liberada o convertida",
            409,
        )
        lot, client = row(db, "lots", data.lot_id), row(db, "clients", data.client_id)
        require(
            lot["entity_id"] == client["entity_id"] == before["entity_id"],
            "Registros de otra lotificadora",
            403,
        )
        require(
            not lot["deleted_at"] and not client["deleted_at"] and client["status"] == "active",
            "Lote o cliente eliminado/inhabilitado",
            409,
        )
        require(
            lot["id"] == before["lot_id"] or lot["status"] == "available", "Lote no disponible", 409
        )
        require(data.expires_on >= today(db), "La nueva fecha de reserva ya venció")
        if lot["id"] != before["lot_id"]:
            db.execute("UPDATE lots SET status='available' WHERE id=?", (before["lot_id"],))
            db.execute("UPDATE lots SET status='reserved' WHERE id=?", (lot["id"],))
        db.execute(
            "UPDATE reservations SET lot_id=?,client_id=?,expires_on=? WHERE id=?",
            (lot["id"], client["id"], str(data.expires_on), identifier),
        )
        after = row(db, "reservations", identifier)
        audit(
            db,
            user,
            "update_reservation",
            before["entity_id"],
            "reservation",
            identifier,
            before=before,
            after=after,
        )
        return after

    @app.put("/api/payments/{identifier}")
    def edit_payment(identifier: int, data: m.PaymentEdit, user: User, db: DB):
        admin(user)
        before = row(db, "payments", identifier)
        authorize(db, user, before["entity_id"], True)
        require(before["status"] == "valid", "Un cobro anulado no se modifica", 409)
        require(data.payment_date <= today(db), "No se aceptan fechas futuras")
        require(data.method == "cash" or data.bank_reference, "Se requiere comprobante bancario")
        db.execute(
            "UPDATE payments SET payment_date=?,method=?,bank_reference=?,notes=? WHERE id=?",
            (str(data.payment_date), data.method, data.bank_reference, data.notes, identifier),
        )
        receipt = db.execute("SELECT * FROM receipts WHERE payment_id=?", (identifier,)).fetchone()
        snapshot = json.loads(receipt["snapshot"])
        snapshot.update(
            payment_date=str(data.payment_date),
            method=data.method,
            bank_reference=data.bank_reference,
        )
        db.execute(
            "UPDATE receipts SET snapshot=?,path=NULL,status='pending' WHERE id=?",
            (json.dumps(snapshot), receipt["id"]),
        )
        after = row(db, "payments", identifier)
        audit(
            db,
            user,
            "update_payment_details",
            before["entity_id"],
            "payment",
            identifier,
            reason=data.reason,
            before=before,
            after=after,
        )
        return after
