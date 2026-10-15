import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Download, MapPin, Plus } from "lucide-react";
import { api } from "./api";
import {
  Field,
  Form,
  Input,
  Modal,
  Pager,
  Picker,
  Select,
  Table,
  useList,
} from "./components";

const blankVertex = () => ({ x: 0, y: 0, neighbor: "" });
const blankSide = () => ({ bearing: "", distance: "", neighbor: "" });
const initial = (today) => ({
  title: "PLANO DE REUNIÓN DE LOTES DE TERRENO",
  plan_kind: "reunion",
  source_plan_ids: [],
  lot_label: "",
  client_id: null,
  road_side: null,
  road_name: "",
  owner: "",
  location: "",
  lot_id: null,
  mode: "vertices",
  crs: "local",
  vertices: [blankVertex(), blankVertex(), blankVertex()],
  sides: [blankSide(), blankSide(), blankSide()],
  origin_x: 0,
  origin_y: 0,
  scale: 250,
  professional: "",
  registration: "",
  plan_date: today,
  notes: "",
});

function Outline({ geometry }) {
  if (!geometry)
    return (
      <div className="empty">
        Valida las coordenadas para ver el dibujo, área y cuadro de
        colindancias.
      </div>
    );
  const points = geometry.points,
    xs = points.map((p) => p[0]),
    ys = points.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const k = Math.min(
    460 / Math.max(maxX - minX, 1),
    240 / Math.max(maxY - minY, 1),
  );
  const mapped = points.map(([x, y]) => [
    280 + (x - (maxX + minX) / 2) * k,
    160 - (y - (maxY + minY) / 2) * k,
  ]);
  return (
    <svg
      viewBox="0 0 560 330"
      className="plan-outline"
      role="img"
      aria-label="Plano del terreno con vértices y medidas"
    >
      <polygon
        points={mapped.map((p) => p.join(",")).join(" ")}
        fill="#edf2e5"
        stroke="#17313b"
        strokeWidth="2"
      />
      {mapped.map(([x, y], i) => {
        const next = mapped[(i + 1) % mapped.length];
        return (
          <g key={i}>
            <circle cx={x} cy={y} r="3" fill="#17313b" />
            <text x={x + 6} y={y - 8}>
              {i + 1}
            </text>
            <text
              x={(x + next[0]) / 2 + 5}
              y={(y + next[1]) / 2 - 7}
              fontSize="11"
            >
              {geometry.sides[i].distance.toFixed(2)} m
            </text>
          </g>
        );
      })}
      <text x="280" y="315" textAnchor="middle">
        Área: {geometry.area_m2.toLocaleString("es-HN")} m² ·{" "}
        {geometry.area_v2.toLocaleString("es-HN")} vara²
      </text>
      <text x="535" y="25">
        N ↑
      </text>
    </svg>
  );
}

function LandMap({ geometry, onPoint, canAdd }) {
  const [online, setOnline] = useState(false),
    [error, setError] = useState(false);
  const container = useRef(null),
    map = useRef(null),
    layer = useRef(null),
    click = useRef(onPoint),
    add = useRef(canAdd);
  click.current = onPoint;
  add.current = canAdd;
  useEffect(() => {
    if (!online) return;
    const view = L.map(container.current).setView([14.6, -86.6], 7);
    map.current = view;
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
    })
      .on("tileerror", () => setError(true))
      .addTo(view);
    view.on("click", (e) => {
      if (add.current)
        click.current({
          x: Number(e.latlng.lng.toFixed(8)),
          y: Number(e.latlng.lat.toFixed(8)),
          neighbor: "",
        });
    });
    return () => {
      view.remove();
      map.current = null;
    };
  }, [online]);
  useEffect(() => {
    if (!map.current) return;
    if (layer.current) {
      layer.current.remove();
      layer.current = null;
    }
    if (geometry?.geographic?.length) {
      layer.current = L.polygon(
        geometry.geographic.map(([x, y]) => [y, x]),
        { color: "#2c6b5c" },
      ).addTo(map.current);
      map.current.fitBounds(layer.current.getBounds(), {
        padding: [35, 35],
        maxZoom: 18,
      });
    }
  }, [online, geometry]);
  return (
    <section className="land-map-section">
      <h3>
        <MapPin size={17} /> Mapa de Honduras
      </h3>
      <p>
        Mapa de referencia de OpenStreetMap. Requiere internet y consulta al
        proveedor el área visible. La cobertura y fecha de actualización varían.
        No muestra límites catastrales certificados.
      </p>
      {!online ? (
        <button
          type="button"
          className="secondary"
          onClick={() => setOnline(true)}
        >
          Activar mapa por internet
        </button>
      ) : (
        <>
          <div className="land-map" ref={container} />
          {canAdd && (
            <p className="muted">
              Haz clic en el mapa para agregar vértices. Para precisión
              topográfica ingresa las coordenadas del levantamiento.
            </p>
          )}
          {error && (
            <p className="error">
              No se pudo cargar parte del mapa. Revisa internet. El plano y el
              cálculo local siguen disponibles.
            </p>
          )}
        </>
      )}
      {geometry && !geometry.geographic.length && (
        <p className="info-box">
          Este plano usa coordenadas locales: no tiene ubicación en el mapa. Usa
          GPS o UTM para georreferenciarlo.
        </p>
      )}
    </section>
  );
}

export function Plans({ entity, today, version, refresh, notify, writable }) {
  const [page, setPage] = useState(1),
    [editing, setEditing] = useState(null);
  const list = useList(`/entities/${entity}/plans?page=${page}`, version);
  const open = async (id) => {
    try {
      setEditing(await api(`/plans/${id}`));
    } catch (err) {
      notify(err.message, true);
    }
  };
  return (
    <>
      <div className="toolbar">
        <p>Planos con área, escala, norte, medidas y colindancias.</p>
        {writable && (
          <button
            className="primary"
            onClick={() => setEditing({ payload: initial(today) })}
          >
            <Plus size={17} /> Nuevo plano
          </button>
        )}
      </div>
      <p className="info-box">
        Los planos se generan con los datos ingresados y requieren revisión y
        firma del profesional responsable. Crear un plano no cambia
        automáticamente el área ni el precio de un lote.
      </p>
      {list.error && <p className="error">{list.error}</p>}
      <div className="panel">
        <Table
          rows={list.items}
          busy={list.busy}
          columns={[
            { key: "title", title: "Plano" },
            {
              key: "area_m2",
              title: "Área m²",
              render: (r) => Number(r.area_m2).toLocaleString("es-HN"),
            },
            {
              key: "updated_at",
              title: "Última actualización",
              render: (r) =>
                new Date(r.updated_at).toLocaleDateString("es-HN", {
                  timeZone: "America/Tegucigalpa",
                }),
            },
            {
              key: "actions",
              title: "",
              render: (r) => (
                <div className="row-actions">
                  <button className="text-button" onClick={() => open(r.id)}>
                    Ver {writable ? "/ editar" : "plano"}
                  </button>
                  <a className="text-button" href={`/api/plans/${r.id}/pdf`}>
                    <Download size={15} /> PDF
                  </a>
                </div>
              ),
            },
          ]}
        />
        <Pager page={page} total={list.total} onChange={setPage} />
      </div>
      {editing && (
        <PlanEditor
          key={editing.id || "new"}
          initialPlan={editing}
          entity={entity}
          writable={writable}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
            notify("Plano guardado");
          }}
        />
      )}
    </>
  );
}

function PlanEditor({ initialPlan, entity, writable, onClose, onSaved }) {
  const [data, setData] = useState({
      ...initial(initialPlan.payload.plan_date),
      ...initialPlan.payload,
    }),
    [geo, setGeo] = useState(initialPlan.geometry || null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [paste, setPaste] = useState("");
  const [ownership, setOwnership] = useState(null),
    [ownerError, setOwnerError] = useState("");
  const sourcePlans = useList(`/entities/${entity}/plans?size=100`, 0);
  useEffect(() => {
    setOwnership(null);
    setOwnerError("");
    if (!data.lot_id) return;
    const abort = new AbortController();
    api(`/lots/${data.lot_id}/plan-owner`, { signal: abort.signal })
      .then((result) => {
        setOwnership(result);
        setData((prev) => ({
          ...prev,
          lot_label: result.code,
          ...(result.contract
            ? {
                client_id: result.contract.client_id,
                owner: result.contract.owner,
              }
            : {
                client_id:
                  initialPlan.payload.lot_id === result.lot_id
                    ? initialPlan.payload.client_id || null
                    : null,
                owner:
                  initialPlan.payload.lot_id === result.lot_id
                    ? initialPlan.payload.owner
                    : "",
              }),
        }));
      })
      .catch((err) => {
        if (err.name !== "AbortError") setOwnerError(err.message);
      });
    return () => abort.abort();
  }, [data.lot_id]);
  const update = (key, value) => {
    setData((prev) => ({ ...prev, [key]: value }));
    setGeo(null);
  };
  const change = (collection, i, key, value) =>
    update(
      collection,
      data[collection].map((r, n) => (n === i ? { ...r, [key]: value } : r)),
    );
  const body = () => ({
    ...data,
    lot_id: data.lot_id ? Number(data.lot_id) : null,
    scale: Number(data.scale),
    origin_x: Number(data.origin_x),
    origin_y: Number(data.origin_y),
    vertices: data.vertices.map((v) => ({
      ...v,
      x: Number(v.x),
      y: Number(v.y),
    })),
    sides:
      data.mode === "bearings"
        ? data.sides.map((s) => ({ ...s, distance: Number(s.distance) }))
        : [],
  });
  async function preview() {
    setBusy(true);
    setError("");
    try {
      setGeo(
        await api(`/entities/${entity}/plans/preview`, {
          method: "POST",
          body: body(),
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={
        initialPlan.id
          ? "Plano #" + initialPlan.id
          : "Nuevo plano de reunión de lotes"
      }
      onClose={onClose}
      wide
    >
      {initialPlan.id && (
        <div className="toolbar">
          <a className="secondary" href={`/api/plans/${initialPlan.id}/pdf`}>
            Descargar PDF guardado
          </a>
          {initialPlan.geometry?.geographic?.length > 0 && (
            <a
              className="secondary"
              href={`/api/plans/${initialPlan.id}/geojson`}
            >
              Exportar GeoJSON
            </a>
          )}
          <small>
            Las descargas corresponden a la última versión guardada.
          </small>
        </div>
      )}
      <fieldset disabled={!writable} className="plan-fieldset">
        <Form
          onCancel={onClose}
          onSubmit={async () => {
            if (!data.lot_id)
              throw new Error("Selecciona el lote al que corresponde el plano");
            if (ownerError) throw new Error(ownerError);
            await api(
              initialPlan.id
                ? `/plans/${initialPlan.id}`
                : `/entities/${entity}/plans`,
              { method: initialPlan.id ? "PUT" : "POST", body: body() },
            );
            onSaved();
          }}
          submit="Guardar plano"
          confirm
        >
          <div className="form-grid">
            <p className="info-box">PLANO DE REUNIÓN DE LOTES DE TERRENO</p>
            <Input
              title="Propietario"
              required
              maxLength={150}
              value={data.owner}
              readOnly
              hint={
                ownership?.contract
                  ? "Cliente actual del contrato #" +
                    ownership.contract.contract_id
                  : "Se consulta al seleccionar el lote."
              }
            />
            <Input
              title="Ubicación del terreno"
              required
              maxLength={250}
              value={data.location}
              onChange={(e) => update("location", e.target.value)}
            />
            <Picker
              title="Lote de referencia"
              entity={entity}
              collection="lots"
              value={data.lot_id || ""}
              onChange={(id) => update("lot_id", id || null)}
            />
            {ownership && !ownership.contract && (
              <Picker
                title="Cliente propietario (lote sin contrato activo)"
                entity={entity}
                collection="clients"
                value={data.client_id || ""}
                onChange={(id, client) => {
                  update("client_id", id || null);
                  update("owner", client?.name || "");
                }}
              />
            )}
            <Input
              title="Referencia del lote"
              readOnly
              value={data.lot_label}
            />
            <Select
              title="Forma de ingreso"
              options={[
                { value: "vertices", label: "Vértices / coordenadas" },
                { value: "bearings", label: "Rumbos o azimuts y distancias" },
              ]}
              value={data.mode}
              onChange={(e) => update("mode", e.target.value)}
            />
            <Select
              title="Sistema de coordenadas"
              options={[
                { value: "local", label: "Local (metros, sin mapa)" },
                {
                  value: "EPSG:4326",
                  label: "GPS WGS84: X longitud / Y latitud",
                },
                {
                  value: "EPSG:32616",
                  label: "UTM WGS84 zona 16 Norte (metros)",
                },
                {
                  value: "EPSG:32617",
                  label: "UTM WGS84 zona 17 Norte (metros)",
                },
              ]}
              value={data.crs}
              onChange={(e) => update("crs", e.target.value)}
            />
            <Input
              title="Escala solicitada 1:"
              type="number"
              min="50"
              max="1000000"
              required
              value={data.scale}
              onChange={(e) => update("scale", e.target.value)}
              hint="Se amplía el denominador si el terreno no cabe. Imprimir al 100%."
            />
            <Input
              title="Fecha del plano"
              type="date"
              required
              value={data.plan_date}
              onChange={(e) => update("plan_date", e.target.value)}
            />
            <Input
              title="Profesional responsable"
              maxLength={150}
              value={data.professional}
              onChange={(e) => update("professional", e.target.value)}
            />
            <Input
              title="Registro / colegiación"
              maxLength={80}
              value={data.registration}
              onChange={(e) => update("registration", e.target.value)}
            />
          </div>
          {ownerError && <p className="error">{ownerError}</p>}
          {data.plan_kind === "reunion" && (
            <details>
              <summary>Reunir planos de lotes contiguos</summary>
              <p>
                Selecciona entre dos y diez planos guardados con coordenadas del
                mismo levantamiento. No cambia los lotes ni sus contratos.
              </p>
              <div className="checks">
                {sourcePlans.items
                  .filter((r) => r.id !== initialPlan.id)
                  .map((r) => (
                    <label key={r.id}>
                      <input
                        type="checkbox"
                        checked={data.source_plan_ids.includes(r.id)}
                        onChange={(e) =>
                          update(
                            "source_plan_ids",
                            e.target.checked
                              ? [...data.source_plan_ids, r.id]
                              : data.source_plan_ids.filter(
                                  (id) => id !== r.id,
                                ),
                          )
                        }
                      />
                      #{r.id} · {r.title} · Lote {r.lot_id || "sin vincular"}
                    </label>
                  ))}
              </div>
              <button
                className="secondary"
                type="button"
                disabled={busy || data.source_plan_ids.length < 2}
                onClick={async () => {
                  setError("");
                  setBusy(true);
                  try {
                    const result = await api(
                      `/entities/${entity}/plans/union`,
                      { method: "POST", body: body() },
                    );
                    setData(result.payload);
                    setGeo(result.geometry);
                  } catch (err) {
                    setError(err.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Calcular contorno de reunión
              </button>
            </details>
          )}
          <div className="form-grid">
            <Select
              title="Lado junto a calle o avenida"
              options={[
                { value: "", label: "Sin calle dibujada" },
                ...(data.mode === "vertices" ? data.vertices : data.sides).map(
                  (_, i) => ({
                    value: String(i),
                    label: `Lado ${i + 1} - ${((i + 1) % (data.mode === "vertices" ? data.vertices.length : data.sides.length)) + 1}`,
                  }),
                ),
              ]}
              value={data.road_side === null ? "" : String(data.road_side)}
              onChange={(e) =>
                update(
                  "road_side",
                  e.target.value === "" ? null : Number(e.target.value),
                )
              }
            />
            <Input
              title="Nombre de calle o avenida"
              maxLength={100}
              value={data.road_name}
              onChange={(e) => update("road_name", e.target.value)}
            />
          </div>
          {data.mode === "vertices" ? (
            <>
              <p>
                Vértices ordenados alrededor del perímetro. X = Este / longitud;
                Y = Norte / latitud. Colindancia del lado que sale de ese
                vértice.
              </p>
              <div className="coordinate-list">
                {data.vertices.map((v, i) => (
                  <div className="coordinate-row" key={i}>
                    <strong>{i + 1}</strong>
                    <Input
                      title="X"
                      type="number"
                      step="any"
                      required
                      value={v.x}
                      onChange={(e) =>
                        change("vertices", i, "x", e.target.value)
                      }
                    />
                    <Input
                      title="Y"
                      type="number"
                      step="any"
                      required
                      value={v.y}
                      onChange={(e) =>
                        change("vertices", i, "y", e.target.value)
                      }
                    />
                    <Input
                      title="Colindancia"
                      maxLength={150}
                      value={v.neighbor}
                      onChange={(e) =>
                        change("vertices", i, "neighbor", e.target.value)
                      }
                    />
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        update(
                          "vertices",
                          data.vertices.filter((_, n) => n !== i),
                        )
                      }
                    >
                      Quitar
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="secondary"
                disabled={data.vertices.length >= 40}
                onClick={() =>
                  update("vertices", [...data.vertices, blankVertex()])
                }
              >
                Agregar vértice
              </button>
              <details>
                <summary>Pegar coordenadas de una lista</summary>
                <Field title="Una fila por vértice: X;Y;Colindancia">
                  <textarea
                    rows={4}
                    value={paste}
                    onChange={(e) => setPaste(e.target.value)}
                    placeholder="0;0;Vecino norte"
                  />
                </Field>
                <button
                  className="secondary"
                  type="button"
                  onClick={() => {
                    try {
                      const rows = paste
                        .trim()
                        .split(/\r?\n/)
                        .map((line) => {
                          const [x, y, ...name] = line.split(";");
                          if (
                            x?.trim() === "" ||
                            y?.trim() === "" ||
                            !Number.isFinite(Number(x)) ||
                            !Number.isFinite(Number(y))
                          )
                            throw Error(
                              "Usa X;Y;Colindancia con decimales separados por punto",
                            );
                          return {
                            x: Number(x),
                            y: Number(y),
                            neighbor: name.join(";"),
                          };
                        });
                      if (rows.length < 3 || rows.length > 40)
                        throw Error("Ingrese entre 3 y 40 vértices");
                      update("vertices", rows);
                      setError("");
                    } catch (err) {
                      setError(err.message);
                    }
                  }}
                >
                  Cargar lista
                </button>
              </details>
            </>
          ) : (
            <>
              <div className="form-grid">
                <Input
                  title="Origen X (Este / longitud)"
                  type="number"
                  step="any"
                  required
                  value={data.origin_x}
                  onChange={(e) => update("origin_x", e.target.value)}
                />
                <Input
                  title="Origen Y (Norte / latitud)"
                  type="number"
                  step="any"
                  required
                  value={data.origin_y}
                  onChange={(e) => update("origin_y", e.target.value)}
                />
              </div>
              <p>
                Incluye todos los lados hasta regresar al inicio. Rumbo:
                N75°07&apos;08&quot;W o azimut decimal de 0 a 360°. En UTM se
                interpreta como rumbo de cuadrícula.
              </p>
              {data.sides.map((s, i) => (
                <div className="coordinate-row" key={i}>
                  <strong>{i + 1}</strong>
                  <Input
                    title="Rumbo / azimut"
                    required
                    value={s.bearing}
                    onChange={(e) =>
                      change("sides", i, "bearing", e.target.value)
                    }
                  />
                  <Input
                    title="Distancia (m)"
                    type="number"
                    step="any"
                    min="0.01"
                    required
                    value={s.distance}
                    onChange={(e) =>
                      change("sides", i, "distance", e.target.value)
                    }
                  />
                  <Input
                    title="Colindancia"
                    maxLength={150}
                    value={s.neighbor}
                    onChange={(e) =>
                      change("sides", i, "neighbor", e.target.value)
                    }
                  />
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      update(
                        "sides",
                        data.sides.filter((_, n) => n !== i),
                      )
                    }
                  >
                    Quitar
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="secondary"
                disabled={data.sides.length >= 40}
                onClick={() => update("sides", [...data.sides, blankSide()])}
              >
                Agregar lado
              </button>
            </>
          )}
          <Field title="Observaciones">
            <textarea
              rows={3}
              maxLength={1000}
              value={data.notes}
              onChange={(e) => update("notes", e.target.value)}
            />
          </Field>
          <div className="toolbar">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={preview}
            >
              {busy ? "Calculando…" : "Validar y dibujar plano"}
            </button>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setData((prev) => ({
                  ...prev,
                  mode: "vertices",
                  crs: "local",
                  vertices: [
                    { x: 0, y: 13.75, neighbor: "Lote número 9" },
                    { x: 26, y: 13.75, neighbor: "Lote número 8" },
                    { x: 26, y: 0, neighbor: "Lote número 11" },
                    { x: 0, y: 0, neighbor: "8 Avenida S.O." },
                  ],
                }));
                setGeo(null);
              }}
            >
              Cargar rectángulo de ejemplo (26 × 13.75 m)
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </Form>
      </fieldset>
      <Outline geometry={geo} />
      {geo && (
        <>
          <div className="info-box">
            Área: <strong>{geo.area_m2.toLocaleString("es-HN")} m²</strong> ·{" "}
            {geo.area_v2.toLocaleString("es-HN")} vara² · Perímetro:{" "}
            {geo.perimeter} m · Error de cierre: {geo.closure_error} m ·{" "}
            {geo.crs}
          </div>
          <Table
            rows={geo.sides.map((s, i) => ({ ...s, id: i }))}
            columns={[
              { key: "side", title: "Lado" },
              { key: "bearing", title: "Rumbo de cuadrícula" },
              { key: "distance", title: "Distancia (m)" },
              { key: "neighbor", title: "Colindancia" },
            ]}
          />
        </>
      )}
      <LandMap
        geometry={geo}
        canAdd={
          writable && data.crs === "EPSG:4326" && data.mode === "vertices"
        }
        onPoint={(point) => {
          const vertices = data.vertices.every(
            (v) => Number(v.x) === 0 && Number(v.y) === 0,
          )
            ? []
            : data.vertices;
          if (vertices.length < 40) update("vertices", [...vertices, point]);
        }}
      />
    </Modal>
  );
}
