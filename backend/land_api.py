import json

from fastapi import Response

from . import land_plans, land_pricing, permissions
from .db import audit, now, setting
from .finance import authorize, require, row
from .models import LandRates


def register(app, User, DB):
    @app.get("/api/modules")
    def modules(user: User):
        return {
            "modules": permissions.MODULES,
            "profiles": {
                profile: permissions.defaults(profile) for profile in ("administrator", "standard")
            },
        }

    @app.get("/api/land-prices")
    def prices(user: User, db: DB):
        return {
            key: setting(db, key)
            for key in ("price_m2", "price_v2", "land_currency", "vara_m2", "land_rate_updated")
        }

    @app.get("/api/entities/{entity}/land-prices")
    def scoped_rates(entity: int, user: User, db: DB):
        authorize(db, user, entity)
        return {**land_pricing.entity_rates(db, entity), "vara_m2": str(land_pricing.factor(db))}

    @app.put("/api/entities/{entity}/land-prices")
    def save_rates(entity: int, data: LandRates, user: User, db: DB):
        from .finance import admin

        admin(user)
        authorize(db, user, entity, True)
        previous = land_pricing.entity_rates(db, entity)
        db.execute(
            "INSERT INTO entity_prices VALUES(?,?,?,?,?) ON CONFLICT(entity_id) DO UPDATE SET price_m2=excluded.price_m2,price_v2=excluded.price_v2,currency=excluded.currency,updated_at=excluded.updated_at",
            (
                entity,
                str(data.price_m2) if data.price_m2 is not None else None,
                str(data.price_v2) if data.price_v2 is not None else None,
                data.currency,
                now(),
            ),
        )
        result = land_pricing.entity_rates(db, entity)
        audit(
            db,
            user,
            "update_entity_prices",
            entity,
            "entity_prices",
            entity,
            before=previous,
            after=result,
        )
        return result

    @app.get("/api/lots/{identifier}/quote")
    def quotation(identifier: int, user: User, db: DB):
        lot = row(db, "lots", identifier)
        authorize(db, user, lot["entity_id"])
        return land_pricing.quote(db, lot)

    @app.get("/api/lots/{identifier}/plan-owner")
    def plan_owner(identifier: int, user: User, db: DB):
        permissions.check(user, "plans")
        lot = row(db, "lots", identifier)
        authorize(db, user, lot["entity_id"])
        contract = db.execute(
            "SELECT c.id contract_id,c.client_id,cl.name owner,cl.document FROM contracts c JOIN clients cl ON cl.id=c.client_id WHERE c.lot_id=? AND c.status='active' ORDER BY c.id DESC LIMIT 1",
            (identifier,),
        ).fetchone()
        return {
            "lot_id": identifier,
            "code": lot["code"],
            "description": lot["description"],
            "contract": dict(contract) if contract else None,
        }

    @app.post("/api/entities/{entity}/plans/preview")
    def preview(entity: int, data: land_plans.Plan, user: User, db: DB):
        authorize(db, user, entity)
        return land_plans.geometry(data, land_pricing.factor(db))

    @app.post("/api/entities/{entity}/plans/union")
    def union(entity: int, data: land_plans.Plan, user: User, db: DB):
        from pyproj import Transformer
        from shapely.geometry import LineString, Polygon
        from shapely.ops import unary_union

        authorize(db, user, entity)
        require(
            len(set(data.source_plan_ids)) == len(data.source_plan_ids)
            and 2 <= len(data.source_plan_ids) <= 10,
            "Seleccione entre dos y diez planos distintos",
        )
        sources = []
        for identifier in data.source_plan_ids:
            source = row(db, "land_plans", identifier)
            require(source["entity_id"] == entity, "Plano de otra lotificadora", 403)
            sources.append(json.loads(source["geometry"]))
        crs = sources[0]["crs"]
        require(
            all((s["crs"] == "local") == (crs == "local") for s in sources),
            "No mezcle planos locales con georreferenciados",
        )
        polygons = []
        exterior_sides = []
        for source in sources:
            points = source["points"]
            if source["crs"] != crs:
                transformer = Transformer.from_crs(source["crs"], crs, always_xy=True)
                points = [transformer.transform(*p) for p in points]
            polygons.append(Polygon(points))
            exterior_sides.extend(
                (LineString([p, points[(i + 1) % len(points)]]), source["sides"][i]["neighbor"])
                for i, p in enumerate(points)
            )
        combined = unary_union(polygons)
        require(
            combined.geom_type == "Polygon" and combined.is_valid and not combined.interiors,
            "Los planos deben ser contiguos por un lado y formar un polígono sin huecos",
        )
        require(
            sum(p.area for p in polygons) - combined.area <= 0.00001,
            "Los planos se superponen; corrija sus límites antes de reunirlos",
        )
        vertices = []
        points = list(combined.exterior.coords)[:-1]
        # Keep only actual direction changes; union may retain intermediate collinear points.
        points = [
            p
            for i, p in enumerate(points)
            if abs(land_plans.cross(points[i - 1], p, points[(i + 1) % len(points)])) > 1e-8
        ]
        require(len(points) <= 40, "El contorno reunido supera 40 vértices")
        for i, (x, y) in enumerate(points):
            edge = LineString([(x, y), points[(i + 1) % len(points)]])
            names = []
            for original, name in exterior_sides:
                if name and original.intersection(edge).length > 0.001 and name not in names:
                    names.append(name)
            vertices.append({"x": x, "y": y, "neighbor": " / ".join(names)[:150]})
        merged = data.model_copy(
            update={
                "mode": "vertices",
                "crs": crs,
                "vertices": [land_plans.Vertex(**v) for v in vertices],
                "plan_kind": "reunion",
                "road_side": None,
            }
        )
        validate_lot(db, user, entity, merged)
        return {
            "payload": merged.model_dump(mode="json"),
            "geometry": land_plans.geometry(merged, land_pricing.factor(db)),
            "source_plan_ids": data.source_plan_ids,
        }

    def validate_lot(db, user, entity, data):
        authorize(db, user, entity, True)
        require(data.lot_id, "Seleccione el lote de referencia del plano")
        if data.lot_id:
            lot = row(db, "lots", data.lot_id)
            require(lot["entity_id"] == entity, "Lote de otra lotificadora", 403)
            contract = db.execute(
                "SELECT client_id FROM contracts WHERE lot_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                (data.lot_id,),
            ).fetchone()
            data.client_id = contract["client_id"] if contract else data.client_id
            require(
                data.client_id,
                "El lote no tiene contrato activo. Seleccione un cliente registrado como propietario del plano",
            )
            owner = row(db, "clients", data.client_id)
            require(owner["entity_id"] == entity, "Cliente de otra lotificadora", 403)
            data.owner = owner["name"]
            data.lot_label = lot["code"]
        for identifier in data.source_plan_ids:
            require(
                row(db, "land_plans", identifier)["entity_id"] == entity,
                "Plano de otra lotificadora",
                403,
            )
        if data.source_plan_ids:
            codes = []
            source_lots = []
            for identifier in data.source_plan_ids:
                source = row(db, "land_plans", identifier)
                require(source["lot_id"], "Cada plano de origen debe estar vinculado a su lote")
                source_lots.append(source["lot_id"])
                reference = row(db, "lots", source["lot_id"])
                contract = db.execute(
                    "SELECT client_id FROM contracts WHERE lot_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                    (source["lot_id"],),
                ).fetchone()
                client = (
                    contract["client_id"]
                    if contract
                    else json.loads(source["payload"]).get("client_id")
                )
                require(
                    client == data.client_id,
                    "Los lotes de la reunión deben tener el mismo cliente propietario",
                )
                codes.append(reference["code"])
            require(
                data.lot_id in source_lots,
                "El lote de referencia debe pertenecer a los planos reunidos",
            )
            require(
                len(source_lots) == len(set(source_lots)), "Seleccione planos de lotes distintos"
            )
            data.lot_label = " / ".join(codes)[:100]

    @app.post("/api/entities/{entity}/plans")
    def create_plan(entity: int, data: land_plans.Plan, user: User, db: DB):
        validate_lot(db, user, entity, data)
        geo = land_plans.geometry(data, land_pricing.factor(db))
        payload = data.model_dump(mode="json")
        identifier = db.execute(
            "INSERT INTO land_plans(entity_id,lot_id,title,payload,geometry,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                entity,
                data.lot_id,
                data.title,
                json.dumps(payload),
                json.dumps(geo),
                user["id"],
                now(),
                now(),
            ),
        ).lastrowid
        audit(
            db,
            user,
            "create_land_plan",
            entity,
            "land_plan",
            identifier,
            after={"payload": payload, "geometry": geo},
        )
        return {"id": identifier, "geometry": geo}

    @app.get("/api/entities/{entity}/plans")
    def list_plans(
        entity: int, user: User, db: DB, page: int = 1, size: int = 30, view: str = "active"
    ):
        authorize(db, user, entity)
        require(page > 0 and 1 <= size <= 100, "Paginación inválida")
        require(view in ("active", "deleted", "all"), "Vista inválida")
        archived = (
            ""
            if view == "all"
            else " AND deleted_at IS " + ("NOT " if view == "deleted" else "") + "NULL"
        )
        return {
            "items": [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,lot_id,deleted_at,created_at,updated_at,json_extract(geometry,'$.area_m2') area_m2 FROM land_plans WHERE entity_id=?"
                    + archived
                    + " ORDER BY id DESC LIMIT ? OFFSET ?",
                    (entity, size, (page - 1) * size),
                )
            ],
            "total": db.execute(
                "SELECT COUNT(*) FROM land_plans WHERE entity_id=?" + archived, (entity,)
            ).fetchone()[0],
        }

    def get(db, user, identifier):
        plan = row(db, "land_plans", identifier)
        authorize(db, user, plan["entity_id"])
        return {
            **plan,
            "payload": json.loads(plan["payload"]),
            "geometry": json.loads(plan["geometry"]),
        }

    @app.get("/api/plans/{identifier}")
    def get_plan(identifier: int, user: User, db: DB):
        return get(db, user, identifier)

    @app.put("/api/plans/{identifier}")
    def edit_plan(identifier: int, data: land_plans.Plan, user: User, db: DB):
        previous = get(db, user, identifier)
        require(not previous["deleted_at"], "Restaure el plano antes de modificarlo", 409)
        validate_lot(db, user, previous["entity_id"], data)
        geo = land_plans.geometry(data, land_pricing.factor(db))
        payload = data.model_dump(mode="json")
        db.execute(
            "UPDATE land_plans SET lot_id=?,title=?,payload=?,geometry=?,updated_at=? WHERE id=?",
            (data.lot_id, data.title, json.dumps(payload), json.dumps(geo), now(), identifier),
        )
        audit(
            db,
            user,
            "update_land_plan",
            previous["entity_id"],
            "land_plan",
            identifier,
            before=previous,
            after={"payload": payload, "geometry": geo},
        )
        return {"id": identifier, "geometry": geo}

    @app.get("/api/plans/{identifier}/pdf")
    def plan_pdf(identifier: int, user: User, db: DB):
        plan = get(db, user, identifier)
        audit(db, user, "export_land_plan_pdf", plan["entity_id"], "land_plan", identifier)
        return Response(
            land_plans.pdf(land_plans.Plan(**plan["payload"]), plan["geometry"]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="plano-{identifier}.pdf"'},
        )

    @app.get("/api/plans/{identifier}/geojson")
    def geojson(identifier: int, user: User, db: DB):
        plan = get(db, user, identifier)
        points = plan["geometry"]["geographic"]
        require(points, "El plano usa coordenadas locales y no tiene ubicación geográfica", 409)
        result = {
            "type": "Feature",
            "properties": {
                "id": identifier,
                "title": plan["title"],
                "area_m2": plan["geometry"]["area_m2"],
            },
            "geometry": {"type": "Polygon", "coordinates": [points + [points[0]]]},
        }
        audit(db, user, "export_land_plan_geojson", plan["entity_id"], "land_plan", identifier)
        return Response(
            json.dumps(result),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="plano-{identifier}.geojson"'},
        )
