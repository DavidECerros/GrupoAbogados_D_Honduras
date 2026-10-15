"""Print layout matching the reunion-plan reference; measured drawing at true scale."""

import io
import math
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from shapely.geometry import Point, Polygon


def render(data, geo):
    output = io.BytesIO()
    width, height = landscape(letter)
    c = canvas.Canvas(output, pagesize=(width, height))
    c.setTitle(data.title)
    ink = colors.HexColor("#14251f")
    style = ParagraphStyle("plan", fontName="Helvetica", fontSize=8, leading=10)

    def text(value, x, top, w, size=9, bold=False, align=0):
        p = Paragraph(
            escape(str(value)).replace("\n", "<br/>"),
            ParagraphStyle(
                "cell",
                parent=style,
                fontSize=size,
                leading=size * 1.25,
                fontName="Helvetica-Bold" if bold else "Helvetica",
                alignment=align,
            ),
        )
        _, h = p.wrap(w, 1000)
        p.drawOn(c, x, top - h)
        return h

    def border():
        c.setStrokeColor(ink)
        c.setLineWidth(1.2)
        c.rect(8, 8, width - 16, height - 16)
        c.rect(12, 12, width - 24, height - 24)

    border()
    text(data.title, 35, height - 23, width - 125, 17, True, 1)
    text("Propietario/a: " + data.owner, 55, height - 57, width - 180, 12, True, 1)
    text("Ubicación del terreno: " + data.location, 55, height - 79, width - 180, 10, False, 1)
    nx, ny = width - 68, height - 73
    for angle, label, tx, ty in [
        (0, "N", 0, 38),
        (90, "E", 38, 0),
        (180, "S", 0, -46),
        (270, "O", -40, 0),
    ]:
        a = math.radians(angle)
        dx, dy = math.sin(a), math.cos(a)
        p = c.beginPath()
        p.moveTo(nx + dx * 30, ny + dy * 30)
        p.lineTo(nx - dy * 5, ny + dx * 5)
        p.lineTo(nx + dy * 5, ny - dx * 5)
        p.close()
        c.setFillColor(ink if angle in (0, 180) else colors.white)
        c.drawPath(p, stroke=1, fill=1)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(nx + tx, ny + ty, label)
    c.rect(28, height - 165, 220, 62)
    text(
        f"Extensión superficial:\n{geo['area_m2']:,.2f} m²\nEquivalente a {geo['area_v2']:,.2f} vara²",
        36,
        height - 111,
        204,
        11,
        True,
        1,
    )
    points = geo["points"]
    minx, miny, maxx, maxy = Polygon(points).bounds
    left, bottom, boxw, boxh = 100, 185, 365, 205
    required = max(data.scale, (maxx - minx) * 2834.64567 / boxw, (maxy - miny) * 2834.64567 / boxh)
    scale = data.scale if required == data.scale else math.ceil(required / 50) * 50
    k = 2834.64567 / scale
    cx = left + boxw / 2
    cy = bottom + boxh / 2
    coords = [
        (cx + (x - (minx + maxx) / 2) * k, cy + (y - (miny + maxy) / 2) * k) for x, y in points
    ]
    path = c.beginPath()
    path.moveTo(*coords[0])
    for p in coords[1:]:
        path.lineTo(*p)
    path.close()
    c.setFillColor(colors.HexColor("#edf2e3"))
    c.setLineWidth(1.5)
    c.drawPath(path, stroke=1, fill=1)
    signed = sum(
        x * coords[(i + 1) % len(coords)][1] - y * coords[(i + 1) % len(coords)][0]
        for i, (x, y) in enumerate(coords)
    )
    c.setFillColor(ink)
    for i, (x, y) in enumerate(coords):
        xx, yy = coords[(i + 1) % len(coords)]
        dx, dy = xx - x, yy - y
        length = max(math.hypot(dx, dy), 1)
        normal = (dy / length, -dx / length) if signed > 0 else (-dy / length, dx / length)
        mx, my = (x + xx) / 2, (y + yy) / 2
        c.setFillColor(colors.white)
        c.circle(x, y, 3.5, fill=1)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 5, y + 9, str(i + 1))
        c.saveState()
        c.translate(mx - normal[0] * 10, my - normal[1] * 10)
        angle = math.degrees(math.atan2(dy, dx))
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180
        c.rotate(angle)
        c.setFont("Helvetica", 9)
        c.drawCentredString(0, 0, f"{geo['sides'][i]['distance']:.2f} m")
        c.restoreState()
        neighbor = geo["sides"][i]["neighbor"]
        if data.road_side == i and data.road_name:
            c.setLineWidth(0.6)
            for offset in (31, 36, 65, 70):
                c.line(
                    x + normal[0] * offset,
                    y + normal[1] * offset,
                    xx + normal[0] * offset,
                    yy + normal[1] * offset,
                )
            c.saveState()
            c.translate(mx + normal[0] * 52, my + normal[1] * 52)
            c.rotate(angle)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(0, 0, data.road_name)
            c.restoreState()
        elif neighbor and len(coords) <= 6:
            if abs(normal[0]) > 0.7:
                text(
                    neighbor,
                    mx + 15 if normal[0] > 0 else mx - 110,
                    my + 10,
                    95,
                    9,
                    False,
                    0 if normal[0] > 0 else 2,
                )
            else:
                text(neighbor, mx + normal[0] * 27 - 55, my + normal[1] * 27 + 7, 110, 9, False, 1)
    if Polygon(coords).covers(Point(cx, cy)) and (maxy - miny) * k > 75 and (maxx - minx) * k > 140:
        text(
            (data.lot_label + "\n" if data.lot_label else "")
            + f"ÁREA TOTAL\n{geo['area_m2']:,.2f} m²\n({geo['area_v2']:,.2f} vara²)",
            cx - 95,
            cy + 34,
            190,
            11,
            True,
            1,
        )
    else:
        text(data.lot_label + f" · {geo['area_m2']:,.2f} m²", left, 155, boxw, 10, True, 1)
    text("CUADRO DE MEDIDAS Y COLINDANCIAS", width - 252, 425, 225, 9, True, 1)

    def side_table(sides, top, max_height):
        rows = [
            [Paragraph(escape(v), style) for v in ["LADO", "RUMBO", "Dist. (m)", "COLINDANCIA"]]
        ]
        for s in sides:
            rows.append(
                [
                    Paragraph(escape(str(v)), style)
                    for v in [
                        s["side"],
                        s["bearing"],
                        f"{s['distance']:.2f}",
                        s["neighbor"] or "Sin registrar",
                    ]
                ]
            )
        t = Table(rows, colWidths=[34, 70, 47, 74])
        t.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.65, ink),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f5ee")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (2, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        _, h = t.wrap(225, 600)
        if h > max_height and len(sides) > 1:
            return side_table(sides[:-1], top, max_height)
        t.drawOn(c, width - 252, top - h)
        return len(sides)

    shown = side_table(geo["sides"][:5], 402, 225)
    text(
        f"Sistema: {geo['crs']} · Perímetro: {geo['perimeter']:.2f} m\n1 vara² = {geo['vara_m2']} m² · Error de cierre: {geo['closure_error']:.4f} m",
        35,
        149,
        460,
        8,
    )
    text(
        "Rumbos referidos al norte de cuadrícula.\nImprimir al 100%, sin ajustar al papel.",
        width - 252,
        151,
        225,
        7,
    )
    text(
        "BORRADOR TÉCNICO. Requiere revisión y firma profesional; no acredita límites ni aprobación registral.",
        28,
        112,
        width - 56,
        7,
    )
    columns = [145, 160, 205, 105, width - 56 - 615]
    contents = [
        ("PROPIETARIO/A", data.owner),
        ("UBICACIÓN", data.location),
        (
            "REVISIÓN PROFESIONAL",
            (data.professional or "Pendiente")
            + "\n"
            + data.registration
            + "\nFirma y sello: __________________",
        ),
        ("FECHA", data.plan_date.isoformat()),
        ("ESCALA", f"1:{scale}"),
    ]
    x = 28
    for w, (heading, value) in zip(columns, contents):
        c.rect(x, 24, w, 78)
        text(heading, x + 6, 95, w - 12, 7, True)
        text(value, x + 6, 79, w - 12, 9)
        x += w
    c.showPage()
    while shown < len(points):
        border()
        text("MEDIDAS Y COLINDANCIAS · CONTINUACIÓN", 35, height - 35, width - 70, 14, True)
        shown += side_table(geo["sides"][shown : shown + 6], height - 90, 420)
        c.showPage()
    for start in range(0, len(points), 20):
        border()
        text("CUADRO DE COORDENADAS · " + geo["crs"], 35, height - 35, width - 70, 14, True)
        text(
            "Vértice · X (Este) · Y (Norte)\n"
            + "\n".join(
                f"{i + 1}: X {x:.4f} · Y {y:.4f}"
                for i, (x, y) in enumerate(points[start : start + 20], start)
            ),
            35,
            height - 80,
            width - 70,
            10,
        )
        c.showPage()
    if data.notes:
        border()
        text("OBSERVACIONES", 35, height - 35, width - 70, 14, True)
        text(data.notes, 35, height - 75, width - 70, 10)
        c.showPage()
    c.save()
    return output.getvalue()
