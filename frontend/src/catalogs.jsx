import { useState } from "react";
import { Edit3, Plus, Trash2, Upload, UserX, UserCheck } from "lucide-react";
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

export function Catalog({ kind, entity, admin, refresh, version, notify }) {
  const [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    [state, setState] = useState(kind === "clients" ? "active" : ""),
    [editing, setEditing] = useState(null),
    [changingStatus, setChangingStatus] = useState(null),
    [statusReason, setStatusReason] = useState(""),
    [deleting, setDeleting] = useState(null);
  const global = kind === "entities";
  const path = global
    ? "/entities"
    : `/entities/${entity}/${kind}?q=${encodeURIComponent(q)}&page=${page}&state=${state}`;
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
            key: "price",
            title: "Precio base",
            render: (r) => money(r.price, r.currency),
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
        {(isClient || admin) && (
          <button
            className="icon"
            aria-label={"Editar " + title}
            onClick={() => setEditing(r)}
          >
            <Edit3 size={16} />
          </button>
        )}
        {isClient && admin && (
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
        {global && (
          <button
            className="icon"
            aria-label={"Eliminar " + r.name}
            onClick={() => setDeleting(r)}
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>
    ),
  });
  return (
    <>
      <div className="toolbar">
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
        {(isClient || admin) && (
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
              ? items.filter((r) =>
                  r.name.toLowerCase().includes(q.toLowerCase()),
                )
              : items
          }
          busy={busy}
        />
        {!global && <Pager total={total} page={page} onChange={setPage} />}
      </div>
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
          kind={kind}
          initial={editing}
          entity={entity}
          admin={admin}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
            notify("Datos guardados");
          }}
        />
      )}
    </>
  );
}

function CatalogForm({ kind, initial, entity, admin, onClose, onSaved }) {
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
          }
        : {
            name: initial.name || "",
            currency: initial.currency || "HNL",
            status: initial.status || "active",
          },
  );
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  async function save() {
    await api(
      initial.id
        ? `/${kind}/${initial.id}`
        : kind === "entities"
          ? "/entities"
          : `/entities/${entity}/${kind}`,
      { method: initial.id ? "PUT" : "POST", body: data },
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
                disabled={initial.id && !admin}
                onChange={(e) => update("name", e.target.value)}
              />
              <Input
                title="Tipo de documento"
                required
                value={data.document_type}
                disabled={initial.id && !admin}
                onChange={(e) => update("document_type", e.target.value)}
              />
              <Input
                title="Número de documento"
                required
                value={data.document}
                disabled={initial.id && !admin}
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
              <Input
                title="Precio base"
                type="number"
                step="0.01"
                min="0.01"
                required
                value={data.price}
                onChange={(e) => update("price", e.target.value)}
              />
              <Select
                title="Moneda"
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
    [password, setPassword] = useState("");
  return (
    <>
      <div className="toolbar">
        <p>Asigna a cada operador las lotificadoras que puede gestionar.</p>
        <button className="primary" onClick={() => setEditing({})}>
          <Plus size={16} /> Nuevo operador
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <Table
          busy={busy}
          rows={items}
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
              render: (r) => <Badge value={r.role} />,
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
  const [data, setData] = useState({
    username: initial.username || "",
    full_name: initial.full_name || "",
    password: "",
    active: initial.active !== 0,
    entity_ids: initial.entity_ids || [],
  });
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  return (
    <Modal
      title={initial.id ? "Editar usuario" : "Nuevo operador"}
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
