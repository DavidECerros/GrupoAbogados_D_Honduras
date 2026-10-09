import { useEffect, useState } from "react";
import { ArrowRightLeft, Banknote, FileText, Plus } from "lucide-react";
import { api, money } from "./api";
import { Details } from "./details";
import {
  Badge,
  Field,
  Form,
  Input,
  Modal,
  Pager,
  Picker,
  SearchBox,
  Select,
  Table,
  useList,
} from "./components";

export function Contracts({
  entity,
  today,
  admin,
  version,
  refresh,
  notify,
  onCollect,
}) {
  const [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    [create, setCreate] = useState(false),
    [selected, setSelected] = useState(null);
  const { items, total, busy, error } = useList(
    `/entities/${entity}/contracts?q=${encodeURIComponent(q)}&page=${page}`,
    version,
  );
  return (
    <>
      <div className="toolbar">
        <SearchBox
          value={q}
          onChange={(value) => {
            setQ(value);
            setPage(1);
          }}
          placeholder="Buscar cliente, documento o lote"
        />
        <button className="primary" onClick={() => setCreate(true)}>
          <Plus size={17} /> Nueva venta
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <Table
          rows={items}
          busy={busy}
          columns={[
            {
              key: "id",
              title: "Contrato",
              render: (r) => <strong>#{r.id}</strong>,
            },
            { key: "client", title: "Cliente" },
            { key: "lot", title: "Lote" },
            {
              key: "price",
              title: "Precio acordado",
              render: (r) => money(r.price, r.currency),
            },
            {
              key: "balance",
              title: "Saldo pendiente",
              render: (r) => money(r.balance, r.currency),
            },
            {
              key: "actions",
              title: "",
              render: (r) => (
                <div className="row-actions">
                  <button
                    className="text-button"
                    onClick={() => setSelected(r.id)}
                  >
                    <FileText size={15} /> Estado de cuenta
                  </button>
                  {r.balance > 0 && (
                    <button
                      className="text-button"
                      onClick={() => onCollect(r.id)}
                    >
                      <Banknote size={15} /> Cobrar
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
        <Pager total={total} page={page} onChange={setPage} />
      </div>
      {create && (
        <SaleForm
          entity={entity}
          today={today}
          onClose={() => setCreate(false)}
          onSaved={() => {
            setCreate(false);
            refresh();
            notify("Venta y cuotas registradas");
          }}
        />
      )}
      {selected && (
        <Account
          identifier={selected}
          entity={entity}
          admin={admin}
          today={today}
          onClose={() => setSelected(null)}
          onCollect={onCollect}
          refresh={refresh}
          notify={notify}
        />
      )}
    </>
  );
}

function SaleForm({ entity, today, onClose, onSaved }) {
  const [data, setData] = useState({
    lot_id: "",
    client_id: "",
    price: "",
    currency: "HNL",
    down_payment: "0",
    installments: 12,
    down_due: today,
    first_due: today,
  });
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  const financed = Math.max(
    0,
    Math.round(Number(data.price || 0) * 100) -
      Math.round(Number(data.down_payment || 0) * 100),
  );
  return (
    <Modal title="Nueva venta" onClose={onClose} wide>
      <Form
        onCancel={onClose}
        submit="Confirmar venta"
        confirm
        confirmationText="Revisé cliente, lote, precio y vencimientos. Confirmo el registro de la venta."
        onSubmit={async () => {
          await api(`/entities/${entity}/contracts`, {
            method: "POST",
            body: { ...data, installments: Number(data.installments) },
          });
          onSaved();
        }}
      >
        <div className="form-grid">
          <Picker
            title="Cliente"
            entity={entity}
            collection="clients"
            value={data.client_id}
            onChange={(id) => update("client_id", id)}
          />
          <Picker
            title="Lote"
            entity={entity}
            collection="lots"
            value={data.lot_id}
            predicate={(r) => r.status !== "sold"}
            onChange={(id, lot) =>
              setData((prev) => ({
                ...prev,
                lot_id: id,
                currency: lot?.currency || "HNL",
                price: lot ? (lot.price / 100).toFixed(2) : "",
              }))
            }
          />
          <Input
            title={"Precio acordado (" + data.currency + ")"}
            type="number"
            min="0.01"
            step="0.01"
            required
            value={data.price}
            onChange={(e) => update("price", e.target.value)}
          />
          <Input
            title="Prima acordada"
            type="number"
            min="0"
            max={data.price || undefined}
            step="0.01"
            required
            value={data.down_payment}
            onChange={(e) => update("down_payment", e.target.value)}
          />
          <Input
            title="Número de cuotas"
            type="number"
            min="1"
            max="600"
            step="1"
            required
            value={data.installments}
            onChange={(e) => update("installments", e.target.value)}
          />
          <Input
            title="Vencimiento de prima"
            type="date"
            required
            value={data.down_due}
            onChange={(e) => update("down_due", e.target.value)}
          />
          <Input
            title="Primer vencimiento mensual"
            type="date"
            required
            value={data.first_due}
            onChange={(e) => update("first_due", e.target.value)}
          />
        </div>
        <div className="info-box">
          Saldo a financiar: <strong>{money(financed, data.currency)}</strong> ·
          Cuota estimada:{" "}
          {money(
            Math.floor(financed / (Number(data.installments) || 1)),
            data.currency,
          )}
          <small className="block">
            La prima seguirá pendiente hasta registrar su pago. Los centavos se
            ajustan en la última cuota.
          </small>
        </div>
      </Form>
    </Modal>
  );
}

export function Account({
  identifier,
  entity,
  admin,
  today,
  onClose,
  onCollect,
  refresh,
  notify,
}) {
  const [account, setAccount] = useState(null),
    [error, setError] = useState(""),
    [action, setAction] = useState(""),
    [version, setVersion] = useState(0),
    [versions, setVersions] = useState(null);
  useEffect(() => {
    api(`/contracts/${identifier}`)
      .then(setAccount)
      .catch((err) => setError(err.message));
  }, [identifier, version]);
  if (action && account)
    return (
      <Modal
        title={
          (action === "transfer" ? "Ceder contrato" : "Modificar condiciones") +
          " · Contrato #" +
          identifier
        }
        onClose={() => setAction("")}
        wide
      >
        <ContractAction
          action={action}
          account={account}
          entity={entity}
          admin={admin}
          today={today}
          onCancel={() => setAction("")}
          onSaved={() => {
            setAction("");
            setVersion((v) => v + 1);
            refresh();
            notify(admin ? "Contrato actualizado" : "Solicitud enviada");
          }}
        />
      </Modal>
    );
  if (versions && account)
    return (
      <Modal
        title={"Versiones · Contrato #" + identifier}
        onClose={() => setVersions(null)}
        wide
      >
        <p>
          Versión actual: <strong>{account.version}</strong>. Aquí se conservan
          las condiciones anteriores.
        </p>
        {!versions.length ? (
          <p>Sin modificaciones anteriores.</p>
        ) : (
          versions.map((r) => (
            <div key={r.id} className="info-box">
              <strong>Versión {r.version}</strong> · {r.reason}
              <Details
                data={JSON.parse(r.snapshot)}
                currency={account.currency}
              />
            </div>
          ))
        )}
        <button className="secondary" onClick={() => setVersions(null)}>
          Volver al estado de cuenta
        </button>
      </Modal>
    );
  return (
    <Modal
      title={"Estado de cuenta · Contrato #" + identifier}
      onClose={onClose}
      wide
    >
      {error && <p className="error">{error}</p>}
      {account ? (
        <>
          <div className="account-summary">
            <div>
              <small>Cliente actual</small>
              <h3>{account.client.name}</h3>
              <p>
                Lote {account.lot.code} · {account.client.document}
              </p>
            </div>
            <div>
              <small>Saldo total</small>
              <h2>{money(account.balance, account.currency)}</h2>
            </div>
          </div>
          <div className="toolbar">
            <span>
              Precio: {money(account.price, account.currency)} · Prima:{" "}
              {money(account.down_payment, account.currency)}
            </span>
            <div className="row-actions">
              {account.balance > 0 && (
                <button
                  className="primary"
                  onClick={() => {
                    onClose();
                    onCollect(identifier);
                  }}
                >
                  <Banknote size={16} /> Cobrar
                </button>
              )}
              <button
                className="secondary"
                onClick={() => setAction("transfer")}
              >
                <ArrowRightLeft size={15} />{" "}
                {admin ? "Ceder contrato" : "Solicitar cesión"}
              </button>
              <button className="secondary" onClick={() => setAction("amend")}>
                {admin ? "Modificar condiciones" : "Solicitar modificación"}
              </button>
              {admin && (
                <button
                  className="text-button"
                  onClick={async () => {
                    try {
                      setVersions(
                        await api(`/contracts/${identifier}/versions`),
                      );
                    } catch (err) {
                      notify(err.message, true);
                    }
                  }}
                >
                  Versiones
                </button>
              )}
            </div>
          </div>
          <h3>Prima y cuotas</h3>
          <Table
            rows={account.obligations}
            columns={[
              {
                key: "number",
                title: "Obligación",
                render: (r) => (r.number === 0 ? "Prima" : "Cuota " + r.number),
              },
              { key: "due_date", title: "Vencimiento" },
              {
                key: "amount",
                title: "Importe",
                render: (r) => money(r.amount, account.currency),
              },
              {
                key: "paid",
                title: "Pagado",
                render: (r) => money(r.paid, account.currency),
              },
              {
                key: "pending",
                title: "Pendiente",
                render: (r) => money(r.amount - r.paid, account.currency),
              },
              {
                key: "state",
                title: "Situación",
                render: (r) => (
                  <Badge
                    value={
                      r.paid === r.amount
                        ? "Pagada"
                        : r.due_date < today
                          ? "Vencida"
                          : "Pendiente"
                    }
                    color={
                      r.paid === r.amount
                        ? "green"
                        : r.due_date < today
                          ? "red"
                          : "yellow"
                    }
                  />
                ),
              },
            ]}
          />
          <h3>Pagos del contrato</h3>
          <Table
            rows={account.payments}
            columns={[
              { key: "folio", title: "Folio" },
              { key: "payment_date", title: "Fecha" },
              {
                key: "received",
                title: "Recibido",
                render: (r) => money(r.received, r.received_currency),
              },
              {
                key: "applied",
                title: "Aplicado",
                render: (r) => money(r.applied, account.currency),
              },
              {
                key: "status",
                title: "Estado",
                render: (r) => <Badge value={r.status} />,
              },
            ]}
          />
          {account.transfers.length > 0 && (
            <>
              <h3>Cesiones</h3>
              {account.transfers.map((r, i) => (
                <p className="info-box" key={i}>
                  {r.effective_date} · Propietario #{r.previous_client} → #
                  {r.new_client} · Saldo transferido{" "}
                  {money(r.balance, account.currency)} · {r.reason}
                </p>
              ))}
            </>
          )}
        </>
      ) : (
        !error && <p>Cargando estado de cuenta…</p>
      )}
    </Modal>
  );
}

function ContractAction({
  action,
  account,
  entity,
  admin,
  today,
  onCancel,
  onSaved,
}) {
  const [reason, setReason] = useState(""),
    [newClient, setNewClient] = useState(""),
    [data, setData] = useState({
      price: (account.price / 100).toFixed(2),
      down_payment: (account.down_payment / 100).toFixed(2),
      installments: account.installments,
      down_due: account.down_due,
      first_due: account.first_due,
    });
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  return (
    <div className="action-card">
      <h3>
        {action === "transfer"
          ? "Cesión de propietario"
          : "Modificación de condiciones"}
      </h3>
      <Form
        onCancel={onCancel}
        submit={admin ? "Confirmar cambio" : "Solicitar autorización"}
        confirm
        onSubmit={async () => {
          const payload =
            action === "transfer"
              ? { new_client_id: newClient, effective_date: today }
              : { ...data, installments: Number(data.installments) };
          if (admin)
            await api(
              `/contracts/${account.id}` +
                (action === "transfer" ? "/transfer" : ""),
              {
                method: action === "transfer" ? "POST" : "PUT",
                body: { ...payload, reason },
              },
            );
          else
            await api(`/entities/${entity}/approvals`, {
              method: "POST",
              body: {
                action:
                  action === "transfer"
                    ? "transfer_contract"
                    : "amend_contract",
                record_id: account.id,
                payload,
                reason,
              },
            });
          onSaved();
        }}
      >
        <div className="form-grid">
          {action === "transfer" ? (
            <>
              <Picker
                title="Nuevo propietario"
                entity={entity}
                collection="clients"
                value={newClient}
                onChange={setNewClient}
              />
              <Input
                title="Fecha efectiva"
                value={today}
                disabled
                hint="La cesión se aplica hoy y conserva los pagos anteriores."
              />
            </>
          ) : (
            <>
              <Input
                title="Precio"
                type="number"
                required
                step="0.01"
                min="0.01"
                value={data.price}
                onChange={(e) => update("price", e.target.value)}
              />
              <Input
                title="Prima"
                type="number"
                required
                step="0.01"
                min="0"
                value={data.down_payment}
                onChange={(e) => update("down_payment", e.target.value)}
              />
              <Input
                title="Cuotas pendientes nuevas"
                type="number"
                required
                min="1"
                max="600"
                value={data.installments}
                onChange={(e) => update("installments", e.target.value)}
              />
              <Input
                title="Vencimiento prima"
                type="date"
                required
                value={data.down_due}
                onChange={(e) => update("down_due", e.target.value)}
              />
              <Input
                title="Primer vencimiento nuevo"
                type="date"
                required
                value={data.first_due}
                onChange={(e) => update("first_due", e.target.value)}
              />
            </>
          )}
        </div>
        {action === "amend" && (
          <p className="info-box">
            Se conserva lo ya pagado y se distribuye el saldo restante en las
            nuevas cuotas. El precio y la prima deben cubrir los importes ya
            pagados. Los recibos anteriores se conservan.
          </p>
        )}
        <Field title="Motivo">
          <textarea
            minLength={3}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
      </Form>
    </div>
  );
}

export function Reservations({
  entity,
  today,
  admin,
  version,
  refresh,
  notify,
}) {
  const [page, setPage] = useState(1),
    [creating, setCreating] = useState(false),
    [selected, setSelected] = useState(null),
    [reason, setReason] = useState(""),
    [data, setData] = useState({
      lot_id: "",
      client_id: "",
      expires_on: today,
    });
  const { items, total, busy, error } = useList(
    `/entities/${entity}/reservations?page=${page}`,
    version,
  );
  return (
    <>
      <div className="toolbar">
        <p>Las reservas vencidas requieren revisión del superusuario.</p>
        <button
          className="primary"
          onClick={() => {
            setData({ lot_id: "", client_id: "", expires_on: today });
            setCreating(true);
          }}
        >
          <Plus size={16} /> Nueva reserva
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <Table
          rows={items}
          busy={busy}
          columns={[
            { key: "lot", title: "Lote" },
            { key: "client", title: "Cliente" },
            { key: "expires_on", title: "Vencimiento" },
            {
              key: "status",
              title: "Estado",
              render: (r) => (
                <Badge
                  value={r.expired ? "Vencida · revisar" : r.status}
                  color={r.expired ? "red" : undefined}
                />
              ),
            },
            {
              key: "action",
              title: "",
              render: (r) =>
                r.status === "active" && (
                  <button
                    className="text-button"
                    onClick={() => {
                      setSelected(r);
                      setReason("");
                    }}
                  >
                    {admin ? "Liberar" : "Solicitar liberación"}
                  </button>
                ),
            },
          ]}
        />
        <Pager total={total} page={page} onChange={setPage} />
      </div>
      {creating && (
        <Modal title="Nueva reserva" onClose={() => setCreating(false)}>
          <Form
            onCancel={() => setCreating(false)}
            onSubmit={async () => {
              await api(`/entities/${entity}/reservations`, {
                method: "POST",
                body: data,
              });
              setCreating(false);
              refresh();
              notify("Reserva registrada");
            }}
            confirm
          >
            <Picker
              title="Cliente"
              entity={entity}
              collection="clients"
              value={data.client_id}
              onChange={(id) => setData((prev) => ({ ...prev, client_id: id }))}
            />
            <Picker
              title="Lote"
              entity={entity}
              collection="lots"
              value={data.lot_id}
              predicate={(r) => r.status === "available"}
              onChange={(id) => setData((prev) => ({ ...prev, lot_id: id }))}
            />
            <Input
              title="Vencimiento"
              type="date"
              min={today}
              required
              value={data.expires_on}
              onChange={(e) =>
                setData((prev) => ({ ...prev, expires_on: e.target.value }))
              }
            />
          </Form>
        </Modal>
      )}
      {selected && (
        <Modal title="Liberación de reserva" onClose={() => setSelected(null)}>
          <Form
            onCancel={() => setSelected(null)}
            confirm
            onSubmit={async () => {
              await api(
                admin
                  ? `/reservations/${selected.id}/release`
                  : `/entities/${entity}/approvals`,
                {
                  method: "POST",
                  body: admin
                    ? { reason }
                    : {
                        action: "release_reservation",
                        record_id: selected.id,
                        reason,
                      },
                },
              );
              setSelected(null);
              refresh();
              notify(admin ? "Reserva liberada" : "Solicitud enviada");
            }}
          >
            <p>
              Lote {selected.lot} · {selected.client}
            </p>
            <Field title="Motivo">
              <textarea
                minLength={3}
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
          </Form>
        </Modal>
      )}
    </>
  );
}
