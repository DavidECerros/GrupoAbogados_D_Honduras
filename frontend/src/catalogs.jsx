import { useEffect, useState } from "react";
import {
  Edit3,
  Plus,
  Trash2,
  Upload,
  UserX,
  UserCheck,
  Download,
} from "lucide-react";
import { CatalogImport } from "./data-tools";
import { EntityRates, RecordActions, RecordFilter } from "./record-tools";
import { api, money } from "./api";
import {
  Badge,
  Field,
  Form,
  Input,
  Modal,
  Pager,
  SearchBox,
  Select,
  Table,
  useList,
} from "./components";

export function Catalog({
  kind,
  entity,
  admin,
  writable = true,
  profile,
  refresh,
  version,
  notify,
}) {
  const [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    [state, setState] = useState(kind === "clients" ? "active" : ""),
    [editing, setEditing] = useState(null),
    [changingStatus, setChangingStatus] = useState(null),
    [statusReason, setStatusReason] = useState(""),
    [importing, setImporting] = useState(false),
    [deleting, setDeleting] = useState(null);
  const [view, setView] = useState("active"),
    [rates, setRates] = useState(null);
  const global = kind === "entities";
  const path = global
    ? "/entities"
    : `/entities/${entity}/${kind}?q=${encodeURIComponent(q)}&page=${page}&state=${view === "deleted" ? "" : state}&view=${view}`;
  const { items, total, busy, error } = useList(path, version);
  const isClient = kind === "clients",
    isLot = kind === "lots";
  const title = isClient ? "cliente" : isLot ? "lote" : "lotificadora";
  const columns = isClient
    ? [
        {
          key: "name",
          title: "Nombre",
          render: (r) => <strong>{r.name}</strong>,
        },
        { key: "document", title: "Documento" },
        { key: "phone", title: "Teléfono" },
        { key: "email", title: "Correo" },
        {
          key: "status",
          title: "Estado",
          render: (r) => <Badge value={r.status} />,
        },
      ]
    : isLot
      ? [
          {
            key: "code",
            title: "Lote",
            render: (r) => <strong>{r.code}</strong>,
          },
          { key: "description", title: "Ubicación" },
          {
            key: "area_m2",
            title: "Área m² / vara²",
            render: (r) => (
              <>
                <strong>{Number(r.area_m2).toLocaleString("es-HN")} m²</strong>
                <small className="block">
                  {Number(r.area_v2).toLocaleString("es-HN")} vara²
                </small>
              </>
            ),
          },
          {
            key: "price",
            title: "Valor de nueva venta",
            render: (r) => (
              <>
                {r.quotation
                  ? money(r.quotation.price, r.quotation.currency)
                  : r.quotation_error}
                <small className="block">
                  {r.pricing_unit === "fixed"
                    ? "Precio fijo"
                    : "Por " + (r.pricing_unit === "m2" ? "m²" : "vara²")}
                </small>
              </>
            ),
          },
          {
            key: "status",
            title: "Estado",
            render: (r) => <Badge value={r.status} />,
          },
        ]
      : [
          {
            key: "name",
            title: "Lotificadora",
            render: (r) => <strong>{r.name}</strong>,
          },
          { key: "currency", title: "Moneda base" },
          {
            key: "status",
            title: "Estado",
            render: (r) => <Badge value={r.status} />,
          },
        ];
  columns.push({
    key: "actions",
    title: "",
    render: (r) => (
      <div className="row-actions">
        {writable && !r.deleted_at && (isClient || isLot || admin) && (
          <button
            className="icon"
            aria-label={"Editar " + title}
            onClick={() => setEditing(r)}
          >
            <Edit3 size={16} />
          </button>
        )}
        {isClient && admin && !r.deleted_at && (
          <button
            className="icon"
            title={
              r.status === "active"
                ? "Inhabilitar cliente"
                : "Reactivar cliente"
            }
            aria-label={
              (r.status === "active" ? "Inhabilitar " : "Reactivar ") + r.name
            }
            onClick={() => {
              setChangingStatus(r);
              setStatusReason("");
            }}
          >
            {r.status === "active" ? (
              <UserX size={16} />
            ) : (
              <UserCheck size={16} />
            )}
          </button>
        )}
        {global && (
          <label className="icon upload" title="Subir logo">
            <Upload size={16} />
            <input
              type="file"
              accept="image/png,image/jpeg"
              aria-label={"Logo de " + r.name}
              onChange={async (e) => {
                if (!e.target.files[0]) return;
                const form = new FormData();
                form.append("file", e.target.files[0]);
                try {
                  await api(`/entities/${r.id}/logo`, {
                    method: "POST",
                    body: form,
                  });
                  notify("Logo guardado");
                  refresh();
                } catch (err) {
                  notify(err.message, true);
                }
              }}
            />
          </label>
        )}
        {!global && (
          <RecordActions
            kind={kind}
            record={r}
            admin={admin}
            refresh={refresh}
            notify={notify}
          />
        )}
        {global && admin && (
          <button className="text-button" onClick={() => setRates(r)}>
            Tarifas m² / vara²
          </button>
        )}
        {global && (
          <RecordActions
            kind="entities"
            record={r}
            admin={admin}
            refresh={refresh}
            notify={notify}
          />
        )}
      </div>
    ),
  });
  return (
    <>
      <div className="toolbar">
        {admin && (
          <RecordFilter
            value={view}
            onChange={(value) => {
              setView(value);
              setPage(1);
            }}
          />
        )}
        <SearchBox
          value={q}
          onChange={(value) => {
            setQ(value);
            setPage(1);
          }}
          placeholder={
            isClient
              ? "Buscar por nombre o documento"
              : "Buscar por lote o ubicación"
          }
        />
        {isClient && (
          <select
            aria-label="Estado del cliente"
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setPage(1);
            }}
          >
            <option value="active">Activos</option>
            <option value="inactive">Inhabilitados</option>
            <option value="">Todos los clientes</option>
          </select>
        )}
        {isLot && (
          <select
            aria-label="Estado del lote"
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos los estados</option>
            <option value="available">Disponible</option>
            <option value="reserved">Reservado</option>
            <option value="sold">Vendido</option>
          </select>
        )}
        {!global && (
          <a
            className="secondary"
            href={`/api/entities/${entity}/catalogs/${kind}/export.xlsx?q=${encodeURIComponent(q)}&state=${view === "deleted" ? "" : state}&view=${view}`}
          >
            <Download size={16} /> Exportar Excel
          </a>
        )}
        {!global && admin && (
          <>
            <a
              className="secondary"
              href={`/api/catalogs/${kind}/template.xlsx`}
            >
              <Download size={16} /> Plantilla
            </a>
            <button className="secondary" onClick={() => setImporting(true)}>
              <Upload size={16} /> Importar
            </button>
          </>
        )}
        {writable && (isClient || isLot || admin) && (
          <button className="primary" onClick={() => setEditing({})}>
            <Plus size={17} /> Nuevo {title}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <Table
          columns={columns}
          rows={
            global
              ? items.filter(
                  (r) =>
                    r.name.toLowerCase().includes(q.toLowerCase()) &&
                    (view === "all" ||
                      r.status ===
                        (view === "deleted" ? "archived" : "active")),
                )
              : items
          }
          busy={busy}
        />
        {!global && <Pager total={total} page={page} onChange={setPage} />}
      </div>
      {importing && (
        <CatalogImport
          kind={kind}
          entity={entity}
          onClose={() => setImporting(false)}
          onSaved={(result) => {
            setImporting(false);
            refresh();
            notify(
              `${result.imported} registros importados. Respaldo: ${result.backup}`,
            );
          }}
        />
      )}
      {changingStatus && (
        <Modal
          title={
            changingStatus.status === "active"
              ? "Inhabilitar cliente"
              : "Reactivar cliente"
          }
          onClose={() => setChangingStatus(null)}
        >
          <Form
            confirm
            onCancel={() => setChangingStatus(null)}
            submit={
              changingStatus.status === "active" ? "Inhabilitar" : "Reactivar"
            }
            onSubmit={async () => {
              const next =
                changingStatus.status === "active" ? "inactive" : "active";
              await api(`/clients/${changingStatus.id}/status`, {
                method: "PATCH",
                body: { status: next, reason: statusReason },
              });
              setChangingStatus(null);
              refresh();
              notify(
                next === "inactive"
                  ? "Cliente inhabilitado; historial conservado"
                  : "Cliente reactivado",
              );
            }}
          >
            <p>
              <strong>{changingStatus.name}</strong>
            </p>
            <p>
              {changingStatus.status === "active"
                ? "Se conservarán sus contratos, pagos y recibos. Podrás seguir cobrando sus contratos actuales, pero no crear nuevas reservas, contratos o cesiones a su nombre. Puedes reactivarlo después."
                : "El cliente volverá a estar disponible para nuevas reservas, contratos y cesiones."}
            </p>
            <Input
              title="Motivo"
              required
              minLength={3}
              maxLength={2000}
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
            />
          </Form>
        </Modal>
      )}
      {deleting && (
        <Modal
          title="Eliminar lotificadora vacía"
          onClose={() => setDeleting(null)}
        >
          <Form
            confirm
            onCancel={() => setDeleting(null)}
            submit="Eliminar"
            onSubmit={async () => {
              await api(`/entities/${deleting.id}`, { method: "DELETE" });
              setDeleting(null);
              refresh();
              notify("Lotificadora vacía eliminada");
            }}
          >
            <p>{deleting.name}</p>
            <p>
              El servidor solo permite eliminar entidades sin registros
              asociados. Las que tienen historial deben archivarse.
            </p>
          </Form>
        </Modal>
      )}
      {editing && (
        <CatalogForm
          key={kind + "-" + (editing.id || "new")}
          kind={kind}
          initial={editing}
          entity={entity}
          admin={admin}
          profile={profile}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
            notify("Datos guardados");
          }}
        />
      )}
      {rates && (
        <EntityRates
          entity={rates}
          notify={notify}
          onClose={() => {
            setRates(null);
            refresh();
          }}
        />
      )}
    </>
  );
}

function CatalogForm({
  kind,
  initial,
  entity,
  admin,
  profile,
  onClose,
  onSaved,
}) {
  const client = kind === "clients",
    lot = kind === "lots";
  const [data, setData] = useState(
    client
      ? {
          name: initial.name || "",
          document_type: initial.document_type || "DNI",
          document: initial.document || "",
          phone: initial.phone || "",
          email: initial.email || "",
          notes: initial.notes || "",
        }
      : lot
        ? {
            code: initial.code || "",
            description: initial.description || "",
            price: initial.price ? (initial.price / 100).toFixed(2) : "",
            currency: initial.currency || "HNL",
            area_m2: initial.area_m2 || "0",
            pricing_unit: initial.pricing_unit || (admin ? "fixed" : "m2"),
          }
        : {
            name: initial.name || "",
            currency: initial.currency || "HNL",
            status: initial.status || "active",
          },
  );
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  const [areaUnit, setAreaUnit] = useState("m2"),
    [conversion, setConversion] = useState(0.697224),
    [prices, setPrices] = useState(null);
  useEffect(() => {
    if (lot)
      api(`/entities/${entity}/land-prices`)
        .then((r) => {
          setConversion(Number(r.vara_m2));
          setPrices(r);
        })
        .catch(() => {});
  }, []);
  async function save() {
    await api(
      initial.id
        ? `/${kind}/${initial.id}`
        : kind === "entities"
          ? "/entities"
          : `/entities/${entity}/${kind}`,
      {
        method: initial.id ? "PUT" : "POST",
        body: lot
          ? {
              ...data,
              price:
                data.pricing_unit === "fixed"
                  ? data.price
                  : data.price || "0.01",
              ...(areaUnit === "v2"
                ? { area_v2: data.area_m2 || "0", area_m2: "0" }
                : { area_m2: data.area_m2 || "0" }),
            }
          : data,
      },
    );
    onSaved();
  }
  return (
    <Modal
      title={
        (initial.id ? "Editar " : "Nuevo ") +
        (client ? "cliente" : lot ? "lote" : "lotificadora")
      }
      onClose={onClose}
    >
      <Form onSubmit={save} onCancel={onClose}>
        <div className="form-grid">
          {client ? (
            <>
              <Input
                title="Nombre completo"
                required
                maxLength={150}
                value={data.name}
                disabled={initial.id && !admin && profile !== "administrator"}
                onChange={(e) => update("name", e.target.value)}
              />
              <Input
                title="Tipo de documento"
                required
                value={data.document_type}
                disabled={initial.id && !admin && profile !== "administrator"}
                onChange={(e) => update("document_type", e.target.value)}
              />
              <Input
                title="Número de documento"
                required
                value={data.document}
                disabled={initial.id && !admin && profile !== "administrator"}
                onChange={(e) => update("document", e.target.value)}
              />
              <Input
                title="Teléfono"
                required
                value={data.phone}
                onChange={(e) => update("phone", e.target.value)}
              />
              <Input
                title="Correo (opcional)"
                type="email"
                value={data.email}
                onChange={(e) => update("email", e.target.value)}
              />
              <Field title="Observaciones">
                <textarea
                  value={data.notes}
                  onChange={(e) => update("notes", e.target.value)}
                  maxLength={2000}
                />
              </Field>
            </>
          ) : lot ? (
            <>
              <Select
                title="Cómo se determina el precio del lote"
                disabled={!admin}
                options={[
                  {
                    value: "fixed",
                    label: "Precio total fijo: usar el valor ingresado",
                  },
                  {
                    value: "m2",
                    label: "Por m²: usar tarifa de esta lotificadora",
                  },
                  {
                    value: "v2",
                    label: "Por vara²: usar tarifa de esta lotificadora",
                  },
                ]}
                value={data.pricing_unit}
                onChange={(e) => update("pricing_unit", e.target.value)}
              />
              <Input
                title="Código del lote"
                required
                value={data.code}
                onChange={(e) => update("code", e.target.value)}
              />
              <Input
                title="Ubicación o descripción"
                value={data.description}
                onChange={(e) => update("description", e.target.value)}
              />
              {data.pricing_unit === "fixed" ? (
                <Input
                  title="Precio total fijo del lote"
                  readOnly={!admin}
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={data.price}
                  onChange={(e) => update("price", e.target.value)}
                />
              ) : (
                <p className="info-box">
                  Precio por superficie. Se usa la tarifa de esta lotificadora:{" "}
                  {prices?.currency}{" "}
                  {data.pricing_unit === "m2"
                    ? prices?.price_m2 || "Sin configurar"
                    : prices?.price_v2 || "Sin configurar"}{" "}
                  por {data.pricing_unit === "m2" ? "m²" : "vara²"}. Para vender
                  por un total como 250,000, selecciona Precio total fijo.
                </p>
              )}
              <Select
                title="Unidad para ingresar el área"
                options={[
                  { value: "m2", label: "Metros cuadrados (m²)" },
                  { value: "v2", label: "Varas cuadradas (vara²)" },
                ]}
                value={areaUnit}
                onChange={(e) => {
                  const unit = e.target.value;
                  update(
                    "area_m2",
                    (
                      Number(data.area_m2) *
                      (unit === "v2" ? 1 / conversion : conversion)
                    ).toFixed(6),
                  );
                  setAreaUnit(unit);
                }}
              />
              <Input
                title={
                  "Área del lote en " + (areaUnit === "m2" ? "m²" : "vara²")
                }
                type="number"
                min="0"
                step="0.000001"
                required
                value={data.area_m2}
                onChange={(e) => update("area_m2", e.target.value)}
                hint={
                  "Equivalente: " +
                  (
                    Number(data.area_m2) *
                    (areaUnit === "m2" ? 1 / conversion : conversion)
                  ).toFixed(4) +
                  (areaUnit === "m2" ? " vara²" : " m²")
                }
              />

              <Select
                title="Moneda"
                disabled={!admin}
                options={["HNL", "USD"]}
                value={data.currency}
                onChange={(e) => update("currency", e.target.value)}
              />
            </>
          ) : (
            <>
              <Input
                title="Nombre"
                required
                value={data.name}
                onChange={(e) => update("name", e.target.value)}
              />
              <Select
                title="Moneda base"
                options={["HNL", "USD"]}
                value={data.currency}
                onChange={(e) => update("currency", e.target.value)}
              />
              <Select
                title="Estado"
                options={["active", "archived"]}
                value={data.status}
                onChange={(e) => update("status", e.target.value)}
              />
            </>
          )}
        </div>
      </Form>
    </Modal>
  );
}

export function Users({ entities, version, refresh, notify }) {
  const { items, busy, error } = useList("/users", version);
  const [editing, setEditing] = useState(null),
    [reset, setReset] = useState(null),
    [password, setPassword] = useState(""),
    [view, setView] = useState("active");
  return (
    <>
      <div className="toolbar">
        <p>
          Asigna rol, lotificadoras y acceso por módulo. Solo el superusuario
          modifica tarifas y permisos.
        </p>
        <RecordFilter value={view} onChange={setView} />
        <button className="primary" onClick={() => setEditing({})}>
          <Plus size={16} /> Nuevo usuario
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <Table
          busy={busy}
          rows={items.filter(
            (r) => view === "all" || Boolean(r.active) === (view === "active"),
          )}
          columns={[
            {
              key: "full_name",
              title: "Usuario",
              render: (r) => (
                <>
                  <strong>{r.full_name}</strong>
                  <small className="block">{r.username}</small>
                </>
              ),
            },
            {
              key: "role",
              title: "Rol",
              render: (r) =>
                r.role === "superuser"
                  ? "Superusuario"
                  : r.profile === "administrator"
                    ? "Administrador"
                    : "Usuario estándar",
            },
            {
              key: "entity_ids",
              title: "Lotificadoras",
              render: (r) =>
                r.role === "superuser"
                  ? "Todas"
                  : r.entity_ids
                      .map((id) => entities.find((e) => e.id === id)?.name)
                      .filter(Boolean)
                      .join(", ") || "Sin acceso",
            },
            {
              key: "active",
              title: "Estado",
              render: (r) => (r.active ? "Activo" : "Desactivado"),
            },
            {
              key: "actions",
              title: "",
              render: (r) => (
                <div className="row-actions">
                  <button className="text-button" onClick={() => setEditing(r)}>
                    Editar
                  </button>
                  <button
                    className="text-button"
                    onClick={() => {
                      setReset(r);
                      setPassword("");
                    }}
                  >
                    Restablecer contraseña
                  </button>
                  {r.role !== "superuser" && (
                    <RecordActions
                      kind="users"
                      record={r}
                      admin
                      refresh={refresh}
                      notify={notify}
                    />
                  )}
                </div>
              ),
            },
          ]}
        />
      </div>
      {editing && (
        <UserForm
          initial={editing}
          entities={entities}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
            notify("Usuario guardado");
          }}
        />
      )}
      {reset && (
        <Modal
          title={"Restablecer contraseña de " + reset.username}
          onClose={() => setReset(null)}
        >
          <Form
            onCancel={() => setReset(null)}
            onSubmit={async () => {
              await api(`/users/${reset.id}/reset-password`, {
                method: "POST",
                body: { password },
              });
              setReset(null);
              refresh();
              notify("Contraseña restablecida; sesiones revocadas");
            }}
            confirm
            confirmationText="Confirmo que se cerrarán las sesiones del usuario y deberá cambiar esta contraseña."
          >
            <Input
              title="Contraseña temporal"
              type="password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Form>
        </Modal>
      )}
    </>
  );
}

function UserForm({ initial, entities, onClose, onSaved }) {
  const [definitions, setDefinitions] = useState(null);
  useEffect(() => {
    api("/modules")
      .then(setDefinitions)
      .catch(() => {});
  }, []);
  const [data, setData] = useState({
    username: initial.username || "",
    full_name: initial.full_name || "",
    password: "",
    active: initial.active !== 0,
    entity_ids: initial.entity_ids || [],
    profile: initial.profile || "standard",
    permissions: initial.permissions || null,
  });
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  return (
    <Modal
      title={initial.id ? "Editar usuario" : "Nuevo usuario"}
      onClose={onClose}
    >
      <Form
        onCancel={onClose}
        onSubmit={async () => {
          const body = initial.id
            ? {
                full_name: data.full_name,
                active: data.active,
                entity_ids: data.entity_ids,
              }
            : {
                username: data.username,
                full_name: data.full_name,
                password: data.password,
                entity_ids: data.entity_ids,
              };
          if (initial.role !== "superuser") {
            body.profile = data.profile;
            body.permissions = data.permissions;
          }
          await api("/users" + (initial.id ? "/" + initial.id : ""), {
            method: initial.id ? "PUT" : "POST",
            body,
          });
          onSaved();
        }}
      >
        <Input
          title="Nombre completo"
          required
          value={data.full_name}
          onChange={(e) => update("full_name", e.target.value)}
        />
        {!initial.id && (
          <>
            <Input
              title="Nombre de acceso"
              required
              pattern="[a-zA-Z0-9_.\-]+"
              value={data.username}
              onChange={(e) => update("username", e.target.value)}
            />
            <Input
              title="Contraseña temporal"
              type="password"
              required
              minLength={12}
              autoComplete="new-password"
              value={data.password}
              onChange={(e) => update("password", e.target.value)}
            />
          </>
        )}
        {initial.role !== "superuser" && (
          <>
            <Select
              title="Rol"
              options={[
                { value: "standard", label: "Usuario estándar" },
                { value: "administrator", label: "Administrador" },
              ]}
              value={data.profile}
              onChange={(e) => {
                update("profile", e.target.value);
                update("permissions", null);
              }}
            />
            <p className="info-box">
              El administrador trabaja en sus lotificadoras asignadas. Tarifas,
              usuarios, respaldos y SQL siguen reservados al superusuario.
            </p>
            {definitions && (
              <div className="permission-grid">
                {Object.entries(definitions.modules).map(([key, title]) => (
                  <Select
                    key={key}
                    title={title + " · " + key}
                    options={[
                      { value: "none", label: "Desactivado" },
                      { value: "read", label: "Solo consulta" },
                      { value: "write", label: "Consulta y edición" },
                    ]}
                    value={
                      (data.permissions || definitions.profiles[data.profile])[
                        key
                      ] || "none"
                    }
                    onChange={(e) =>
                      update("permissions", {
                        ...(data.permissions ||
                          definitions.profiles[data.profile]),
                        [key]: e.target.value,
                      })
                    }
                  />
                ))}
              </div>
            )}
            <Field title="Lotificadoras permitidas">
              <div className="checks">
                {entities.map((entity) => (
                  <label key={entity.id}>
                    <input
                      type="checkbox"
                      checked={data.entity_ids.includes(entity.id)}
                      onChange={(e) =>
                        update(
                          "entity_ids",
                          e.target.checked
                            ? [...data.entity_ids, entity.id]
                            : data.entity_ids.filter((id) => id !== entity.id),
                        )
                      }
                    />
                    {entity.name}
                  </label>
                ))}
              </div>
            </Field>
            {initial.id && (
              <label className="confirmation">
                <input
                  type="checkbox"
                  checked={data.active}
                  onChange={(e) => update("active", e.target.checked)}
                />
                Cuenta activa
              </label>
            )}
          </>
        )}
      </Form>
    </Modal>
  );
}
