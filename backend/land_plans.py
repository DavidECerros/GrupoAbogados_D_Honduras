"""Coordinate based plans. No network calls or inferred cadastral boundaries."""

import math
import re
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pyproj import Transformer

from .finance import require
from .models import Model

PLAN_TITLE = "PLANO DE REUNIÓN DE LOTES DE TERRENO"


class Vertex(Model):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    neighbor: str = Field(default="", max_length=150)


class Side(Model):
    bearing: str = Field(min_length=1, max_length=60)
    distance: float = Field(gt=0, le=100000, allow_inf_nan=False)
    neighbor: str = Field(default="", max_length=150)


class Plan(Model):
    client_id: int | None = None
    plan_kind: Literal["reunion", "desmembramiento"] = "reunion"
    lot_label: str = Field(default="", max_length=100)
    source_plan_ids: list[int] = Field(default=[], max_length=10)
    road_side: int | None = Field(default=None, ge=0, lt=40)
    road_name: str = Field(default="", max_length=100)
    title: str = Field(default="PLANO DE REUNIÓN DE LOTES DE TERRENO", min_length=1, max_length=150)
    owner: str = Field(default="", max_length=150)
    location: str = Field(min_length=1, max_length=250)
    lot_id: int | None = None
    mode: Literal["vertices", "bearings"] = "vertices"
    crs: Literal["local", "EPSG:4326", "EPSG:32616", "EPSG:32617"] = "local"
    vertices: list[Vertex] = Field(default=[], max_length=40)
    sides: list[Side] = Field(default=[], max_length=40)
    origin_x: float = Field(default=0, allow_inf_nan=False)
    origin_y: float = Field(default=0, allow_inf_nan=False)
    scale: int = Field(default=250, ge=50, le=1000000)
    professional: str = Field(default="", max_length=150)
    registration: str = Field(default="", max_length=80)
    plan_date: date = Field(
        default_factory=lambda: datetime.now(ZoneInfo("America/Tegucigalpa")).date()
    )
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def fixed_title(self):
        self.title = PLAN_TITLE
        return self


def azimuth(text):
    try:
        result = float(text)
        require(
            math.isfinite(result) and 0 <= result < 360, "Azimut debe estar entre 0 y 360 grados"
        )
        return result
    except ValueError:
        match = re.fullmatch(
            r'([NS])\s*(\d+(?:\.\d+)?)\s*(?:[°º]\s*(\d+(?:\.\d+)?)\s*[\'’′]?\s*(\d+(?:\.\d+)?)?\s*["”″]?)?\s*([EWO])',
            text.upper(),
        )
        require(match, "Rumbo inválido. Use N75°07'08\"W o azimut decimal (0 a 360)")
        ns, degrees, minutes, seconds, ew = match.groups()
        minutes, seconds = float(minutes or 0), float(seconds or 0)
        angle = float(degrees) + minutes / 60 + seconds / 3600
        require(angle <= 90 and minutes < 60 and seconds < 60, "Rumbo fuera de rango")
        return (
            (angle if ew == "E" else 360 - angle) % 360
            if ns == "N"
            else (180 - angle if ew == "E" else 180 + angle)
        )


def bearing_text(angle):
    angle %= 360
    ns, ew = ("N" if angle <= 90 or angle >= 270 else "S"), ("E" if angle <= 180 else "W")
    value = min(angle, 360 - angle) if ns == "N" else abs(180 - angle)
    total = round(value * 3600)
    d, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{ns} {d}°{m:02}'{s:02}\" {ew}"


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def intersects(a, b, c, d):
    v = [cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)]
    if v[0] * v[1] < 0 and v[2] * v[3] < 0:
        return True
    return any(
        abs(n) < 1e-8
        and min(p[0], q[0]) - 1e-8 <= r[0] <= max(p[0], q[0]) + 1e-8
        and min(p[1], q[1]) - 1e-8 <= r[1] <= max(p[1], q[1]) + 1e-8
        for n, p, q, r in [(v[0], a, b, c), (v[1], a, b, d), (v[2], c, d, a), (v[3], c, d, b)]
    )


def geometry(data, vara_m2):
    crs = data.crs
    closure = 0
    if data.mode == "vertices":
        require(
            len(data.vertices) >= 3,
            "Ingrese al menos tres vértices ordenados alrededor del terreno",
        )
        raw = [(v.x, v.y) for v in data.vertices]
        neighbors = [v.neighbor for v in data.vertices]
        if raw[0] == raw[-1]:
            raw, neighbors = raw[:-1], neighbors[:-1]
        if crs == "EPSG:4326":
            crs = "EPSG:32616" if sum(p[0] for p in raw) / len(raw) < -84 else "EPSG:32617"
            transform = Transformer.from_crs(4326, crs, always_xy=True)
            points = [transform.transform(*p) for p in raw]
        else:
            points = raw
    else:
        require(
            3 <= len(data.sides) <= 40, "Ingrese entre 3 y 40 lados, incluido el regreso al inicio"
        )
        origin = (data.origin_x, data.origin_y)
        if crs == "EPSG:4326":
            crs = "EPSG:32616" if data.origin_x < -84 else "EPSG:32617"
            origin = Transformer.from_crs(4326, crs, always_xy=True).transform(*origin)
        points, neighbors, perimeter = [origin], [], 0
        for side in data.sides:
            angle = math.radians(azimuth(side.bearing))
            x, y = points[-1]
            points.append(
                (x + side.distance * math.sin(angle), y + side.distance * math.cos(angle))
            )
            neighbors.append(side.neighbor)
            perimeter += side.distance
        closure = math.dist(points[-1], points[0])
        require(
            closure <= max(0.05, perimeter / 1000),
            f"La poligonal no cierra: error {closure:.3f} m. Corrija los rumbos y distancias",
        )
        points.pop()
    require(
        len(points) >= 3 and len(set(points)) == len(points), "Vértices repetidos o insuficientes"
    )
    require(
        all(
            math.isfinite(x) and math.isfinite(y) and abs(x) < 1e8 and abs(y) < 1e8
            for x, y in points
        ),
        "Coordenadas fuera de rango",
    )
    count = len(points)
    for i in range(count):
        require(
            math.dist(points[i], points[(i + 1) % count]) >= 0.01,
            "Lados menores de un centímetro o vértices repetidos",
        )
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            require(
                not intersects(
                    points[i], points[(i + 1) % count], points[j], points[(j + 1) % count]
                ),
                "Los lados del polígono se cruzan o se tocan",
            )
    base = points[0]
    relative = [(x - base[0], y - base[1]) for x, y in points]
    area = (
        abs(
            sum(
                x * relative[(i + 1) % count][1] - y * relative[(i + 1) % count][0]
                for i, (x, y) in enumerate(relative)
            )
        )
        / 2
    )
    require(area >= 0.01, "Área nula o terreno degenerado")
    geographic = []
    if crs != "local":
        transform = Transformer.from_crs(crs, 4326, always_xy=True)
        geographic = [list(transform.transform(x, y)) for x, y in points]
        require(
            all(-89.7 <= lon <= -82 and 12.8 <= lat <= 17.7 for lon, lat in geographic),
            "Coordenadas fuera del entorno de Honduras; revise sistema, zona y orden X/Y",
        )
    sides = []
    for i, (x, y) in enumerate(points):
        other = points[(i + 1) % count]
        sides.append(
            {
                "side": f"{i + 1} - {(i + 1) % count + 1}",
                "bearing": bearing_text(math.degrees(math.atan2(other[0] - x, other[1] - y))),
                "distance": round(math.dist((x, y), other), 4),
                "neighbor": neighbors[i],
            }
        )
    return {
        "points": points,
        "geographic": geographic,
        "crs": crs,
        "area_m2": round(area, 6),
        "area_v2": round(area / float(vara_m2), 6),
        "vara_m2": str(vara_m2),
        "perimeter": round(sum(s["distance"] for s in sides), 4),
        "closure_error": round(closure, 4),
        "sides": sides,
    }


def pdf(data, geo):
    from .plan_pdf import render

    return render(data, geo)
