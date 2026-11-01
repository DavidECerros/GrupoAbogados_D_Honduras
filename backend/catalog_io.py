"""Spreadsheet interchange for the two editable catalogs."""

import csv
import hashlib
import io
import json
import zipfile
from copy import copy
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from pydantic import ValidationError

from . import lot_details, models
from .db import audit, catalog_id, now
from .finance import require
from .land_pricing import areas, describe

FIELDS = {
    "clients": [
        ("id", "ID"),
        ("name", "Nombre"),
        ("document_type", "Tipo de documento"),
        ("document", "Documento"),
        ("phone", "Teléfono"),
        ("email", "Correo"),
        ("notes", "Observaciones"),
        ("status", "Estado"),
    ],
    "lots": [
        ("id", "ID"),
        ("code", "Código"),
        ("description", "Descripción"),
        ("price", "Precio"),
        ("currency", "Moneda"),
        ("status", "Estado"),
        ("area_m2", "Área m²"),
        ("area_v2", "Área vara²"),
        ("pricing_unit", "Unidad de precio"),
        ("registered_client_id", "ID cliente registrado"),
        ("deed_client_name", "Cliente según escritura"),
        ("deed_client_document", "Documento del cliente"),
        ("deed_client_phone", "Teléfono del cliente"),
        ("deed_client_email", "Correo del cliente"),
        ("deed_address", "Dirección según escritura"),
        ("boundaries", "Medidas y colindancias JSON"),
    ],
}
STATUS = {
    "Activo": "active",
    "Inhabilitado": "inactive",
    "Disponible": "available",
    "Reservado": "reserved",
    "Vendido": "sold",
}


def kind_valid(kind):
    require(kind in FIELDS, "Catálogo inválido", 404)


def template(kind):
    kind_valid(kind)
    book = load_workbook(Path(__file__).with_name("templates") / (kind + ".xlsx"))
    if kind == "lots":
        sheet = book["Lotes"]
        for column, (_, title) in enumerate(FIELDS[kind], 1):
            cell = sheet.cell(1, column, title)
            cell._style = copy(sheet.cell(1, 1)._style)
        sheet.auto_filter.ref = f"A1:P{sheet.max_row}"
        instructions = book["Instrucciones"]
        instructions.append(
            [
                "Ficha de escritura: cliente, documento, teléfono, correo y dirección conservan el texto ingresado."
            ]
        )
        instructions.append(
            ["ID cliente registrado es opcional y debe pertenecer a la misma lotificadora."]
        )
        instructions.append(
            [
                "Precio vacío: ficha pendiente de precio, no disponible para venta hasta configurarlo."
            ]
        )
        instructions.append(["Medidas y colindancias JSON: lista de lados. Ejemplo:"])
        instructions.append(
            ['[{"side":"Norte","bearing":"","distance":"26.00","neighbor":"Lote 9"}]']
        )
        instructions.append(
            [
                "Las plantillas anteriores siguen siendo válidas y conservan los datos nuevos al actualizar."
            ]
        )
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()


def fingerprint(db, entity, kind):
    payload = [
        dict(r)
        for r in db.execute(f"SELECT * FROM {kind} WHERE entity_id=? ORDER BY id", (entity,))
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def export_catalog(db, entity, kind, q="", state="", view="active"):
    kind_valid(kind)
    search = (
        "(name LIKE ? OR document LIKE ?)"
        if kind == "clients"
        else "(code LIKE ? OR description LIKE ? OR deed_address LIKE ? OR deed_client_name LIKE ? OR deed_client_document LIKE ?)"
    )
    require(view in ("active", "deleted", "all"), "Vista inválida")
    archived = (
        ""
        if view == "all"
        else " AND deleted_at IS " + ("NOT " if view == "deleted" else "") + "NULL"
    )
    rows = db.execute(
        f"SELECT * FROM {kind} WHERE entity_id=? AND {search} AND (?='' OR status=?)"
        + archived
        + " ORDER BY id",
        (entity, *([f"%{q}%"] * (2 if kind == "clients" else 5)), state, state),
    ).fetchall()
    book = Workbook()
    sheet = book.active
    sheet.title = "Clientes" if kind == "clients" else "Lotes"
    sheet.append([title for field, title in FIELDS[kind]])
    for record in rows:
        if kind == "lots":
            record = describe(db, dict(record))
        values = []
        for field, title in FIELDS[kind]:
            value = record[field]
            if field in ("price", "area_m2", "area_v2") and value is not None:
                value = Decimal(value) / (100 if field == "price" else 1)
            if field == "boundaries":
                value = json.dumps(value, ensure_ascii=False)
            if field == "status":
                value = next((label for label, code in STATUS.items() if code == value), value)
            values.append(value)
        sheet.append(values)
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = "s"  # Keep literal strings, including leading '=', as text.
                cell.number_format = "@"
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="17313B")
        cell.font = Font(color="FFFFFF", bold=True)
    for index, (field, title) in enumerate(FIELDS[kind], 1):
        from openpyxl.utils import get_column_letter

        sheet.column_dimensions[get_column_letter(index)].width = (
            36 if field in ("name", "description", "notes") else 24
        )
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_view.showGridLines = False
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()


def read_file(content, filename, kind):
    kind_valid(kind)
    require(len(content) <= 12_000_000, "Archivo máximo 12 MB")
    if filename.lower().endswith(".xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                require(
                    sum(item.file_size for item in archive.infolist()) <= 100_000_000,
                    "Excel descomprimido demasiado grande",
                )
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
            sheet = book["Clientes" if kind == "clients" else "Lotes"]
            records = []
            for row in sheet.iter_rows():
                require(len(records) <= 10000, "Máximo 10,000 filas")
                require(
                    not any(cell.data_type == "f" for cell in row),
                    "No se admiten fórmulas en la hoja de datos",
                )
                records.append([cell.value for cell in row])
            book.close()
        except (zipfile.BadZipFile, KeyError, ValueError, OSError):
            require(False, "Excel inválido. Use la hoja Clientes o Lotes de la plantilla")
    else:
        require(filename.lower().endswith(".csv"), "Use .xlsx o .csv")
        try:
            text = content.decode("utf-8-sig")
            delimiter = (
                ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
            )
            records = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        except (UnicodeError, IndexError, csv.Error):
            require(False, "CSV inválido; guárdelo como UTF-8")
    require(records and len(records) <= 10001, "Archivo vacío o más de 10,000 filas")
    headers = [str(value or "").strip() for value in records[0]]
    expected = dict((title, field) for field, title in FIELDS[kind])
    require(len(headers) == len(set(headers)), "Encabezados duplicados")
    required = set(expected) - (
        {"Área m²", "Área vara²", "Unidad de precio"}
        | {title for key, title in FIELDS["lots"] if key in lot_details.DEED_FIELDS}
        if kind == "lots"
        else set()
    )
    require(
        required.issubset(headers) and set(headers).issubset(expected),
        "Los encabezados deben coincidir con la plantilla",
    )
    return [
        (
            index,
            {
                expected[title]: values[col] if col < len(values) else None
                for col, title in enumerate(headers)
            },
        )
        for index, values in enumerate(records[1:], 2)
        if any(value not in (None, "") for value in values)
    ]


def plan_import(db, entity, kind, records, mode):
    require(mode in ("create", "upsert"), "Modo de importación inválido")
    errors, changes, seen = [], [], set()
    for line, values in records:
        try:
            values = dict(values)
            identifier = values.pop("id")
            require(
                identifier in (None, "") or (str(identifier).isdigit() and int(identifier) > 0),
                "ID debe ser un entero positivo o estar vacío",
            )
            identifier = int(identifier) if identifier not in (None, "") else None
            raw_status = str(values.pop("status") or "").strip()
            status = STATUS.get(raw_status, raw_status)
            for key, value in list(values.items()):
                if kind == "lots" and key == "boundaries":
                    values[key] = json.loads(value) if value else []
                elif kind == "lots" and key == "registered_client_id":
                    if value not in (None, ""):
                        require(
                            Decimal(str(value)) == int(value),
                            "ID cliente registrado debe ser entero",
                        )
                    values[key] = int(value) if value not in (None, "") else None
                elif kind == "lots" and key == "price" and value in (None, ""):
                    values[key] = None
                elif key in ("area_m2", "area_v2", "pricing_unit") and value in (None, ""):
                    values.pop(key)
                elif key not in ("price", "area_m2", "area_v2"):
                    require(
                        not isinstance(value, (int, float)),
                        f"{key}: use texto para conservar ceros iniciales",
                    )
                    values[key] = str(value or "").strip()
            data = (models.Client if kind == "clients" else models.Lot)(**values).model_dump(
                mode="json", exclude_unset=(kind == "lots")
            )
            natural = (
                (data["document_type"], data["document"]) if kind == "clients" else (data["code"],)
            )
            key_sql = "document_type=? AND document=?" if kind == "clients" else "code=?"
            previous = db.execute(
                f"SELECT * FROM {kind} WHERE entity_id=? AND {key_sql}", (entity, *natural)
            ).fetchone()
            if identifier:
                identified = db.execute(
                    f"SELECT * FROM {kind} WHERE id=? AND entity_id=?", (identifier, entity)
                ).fetchone()
                require(identified is not None, "ID no pertenece a esta lotificadora")
                require(
                    previous is None or previous["id"] == identifier, "Documento o código duplicado"
                )
                previous = identified
            require(
                mode == "upsert" or previous is None,
                "Registro existente; seleccione Crear y actualizar",
            )
            require(
                previous is None or not previous["deleted_at"],
                "El registro está eliminado. Restáurelo antes de importar cambios",
                409,
            )
            record_key = ("id", previous["id"]) if previous else natural
            require(
                record_key not in seen and natural not in seen, "Registro repetido en el archivo"
            )
            seen.add(record_key)
            seen.add(natural)
            if kind == "clients":
                status = status or (previous["status"] if previous else "active")
                require(status in ("active", "inactive"), "Estado debe ser Activo o Inhabilitado")
                data["status"] = status
            else:
                if previous:
                    if "area_m2" not in values and "area_v2" not in values:
                        data["area_m2"] = previous["area_m2"]
                    if "pricing_unit" not in values:
                        data["pricing_unit"] = previous["pricing_unit"]
                data["area_m2"] = areas(db, models.Lot(**data))
                data.pop("area_v2", None)
                lot_details.storage(
                    db, entity, models.Lot(**data), dict(previous) if previous else None
                )
                require(
                    not status or status == (previous["status"] if previous else "available"),
                    "El estado del lote depende de reservas y contratos; no se importa",
                )
            changes.append(
                {
                    "line": line,
                    "operation": "update" if previous else "create",
                    "id": previous["id"] if previous else None,
                    "data": data,
                }
            )
        except (ValidationError, ValueError, TypeError) as exc:
            errors.append(
                {"line": line, "message": str(exc).split("For further information")[0][:600]}
            )
        except Exception as exc:
            from fastapi import HTTPException

            if not isinstance(exc, HTTPException):
                raise
            errors.append({"line": line, "message": str(exc.detail)})
    require(records, "No hay filas para importar")
    return changes, errors


def apply_import(db, user, entity, kind, changes, reason):
    for item in changes:
        data, identifier = dict(item["data"]), item["id"]
        if kind == "lots":
            model = models.Lot(**data)
            previous = (
                dict(db.execute("SELECT * FROM lots WHERE id=?", (identifier,)).fetchone())
                if identifier
                else None
            )
            data = lot_details.storage(db, entity, model, previous)
        fields = list(data)
        if identifier:
            before = dict(db.execute(f"SELECT * FROM {kind} WHERE id=?", (identifier,)).fetchone())
            db.execute(
                f"UPDATE {kind} SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?",
                (*data.values(), identifier),
            )
        else:
            before = None
            data["id"] = catalog_id(db, kind)
            data["entity_id"] = entity
            if kind == "clients":
                data.update(created_by=user["id"], created_at=now())
            identifier = db.execute(
                f"INSERT INTO {kind}("
                + ",".join(data)
                + ") VALUES("
                + ",".join("?" for _ in data)
                + ")",
                tuple(data.values()),
            ).lastrowid
        after = dict(db.execute(f"SELECT * FROM {kind} WHERE id=?", (identifier,)).fetchone())
        audit(
            db,
            user,
            "import_" + kind,
            entity,
            kind,
            identifier,
            reason=reason,
            before=before,
            after=after,
        )
