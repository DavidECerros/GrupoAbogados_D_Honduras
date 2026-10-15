import { useEffect, useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import { api, money } from "./api";
import { Form, Input, Modal, Select } from "./components";

export function RecordFilter({ value, onChange }) {
  return (
    <Select
      title="Mostrar registros"
      options={[
        { value: "active", label: "Vigentes" },
        { value: "deleted", label: "Eliminados / anulados" },
        { value: "all", label: "Todos (incluido historial)" },
      ]}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function RecordActions({ kind, record, admin, refresh, notify }) {
  const [open, setOpen] = useState(false),
    [purge, setPurge] = useState(false),
    [reason, setReason] = useState("");
  if (!admin) return null;
  const removed =
    kind === "entities"
      ? record.status === "archived"
      : kind === "contracts"
        ? record.status === "cancelled"
        : kind === "users"
          ? !record.active
          : Boolean(record.deleted_at);
  const label = purge
    ? "Eliminar definitivamente"
    : removed
      ? "Restaurar"
      : kind === "contracts" || kind === "payments"
        ? "Anular"
        : kind === "entities"
          ? "Archivar"
          : kind === "approvals"
            ? "Retirar solicitud"
            : kind === "users"
              ? "Desactivar"
              : "Eliminar";
  return (
    <>
      <button
        type="button"
        className="icon danger-text"
        aria-label={label + " registro #" + record.id}
        title={label}
        onClick={() => {
          setPurge(false);
          setReason("");
          setOpen(true);
        }}
      >
        {removed ? <RotateCcw size={16} /> : <Trash2 size={16} />}
      </button>
      {removed && ["lots", "clients"].includes(kind) && (
        <button
          type="button"
          className="text-button danger-text"
          onClick={() => {
            setPurge(true);
            setReason("");
            setOpen(true);
          }}
        >
          Eliminar definitivamente
        </button>
      )}
      {open && (
        <Modal
          title={label + " registro #" + record.id}
          onClose={() => {
            setOpen(false);
            setPurge(false);
          }}
        >
          <Form
            onCancel={() => {
              setOpen(false);
              setPurge(false);
            }}
            submit={label}
            confirm
            onSubmit={async () => {
              const result = await api(`/${kind}/${record.id}/lifecycle`, {
                method: "POST",
                body: {
                  action: purge ? "purge" : removed ? "restore" : "delete",
                  reason,
                },
              });
              setOpen(false);
              setPurge(false);
              refresh();
              notify(
                label + ": operación registrada con respaldo " + result.backup,
              );
            }}
          >
            <p>
              {record.code ||
                record.name ||
                record.full_name ||
                record.title ||
                record.client ||
                "Registro #" + record.id}
            </p>
            <p className="info-box">
              {purge
                ? "Se borrará de la base de datos y se liberará su código o documento. Solo se permite si no tiene contratos, reservas ni otras referencias. Se crea un respaldo previo y se conserva la auditoría. No se puede restaurar desde esta lista."
                : removed
                  ? "El registro volverá a la lista de vigentes. Se conserva su historial."
                  : kind === "contracts"
                    ? "Se conservará el contrato y su historial. Para anularlo no debe tener cobros vigentes. El lote quedará disponible. La reactivación requiere que siga disponible."
                    : kind === "payments"
                      ? "Se conservará el cobro anulado y se restituirá su aplicación al saldo; no implica devolver dinero automáticamente."
                      : kind === "users"
                        ? "Se desactivará el acceso y se cerrarán las sesiones. El historial se conserva."
                        : "El registro se quitará de la lista de vigentes y podrás restaurarlo desde Eliminados / anulados. Se conservarán sus relaciones e historial."}
            </p>
            <Input
              title="Motivo"
              required
              minLength={3}
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Form>
        </Modal>
      )}
    </>
  );
}

export function EntityRates({ entity, onClose, notify }) {
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    api(`/entities/${entity.id}/land-prices`)
      .then((r) =>
        setData({
          price_m2: r.price_m2 || "",
          price_v2: r.price_v2 || "",
          currency: r.currency,
        }),
      )
      .catch((e) => setError(e.message));
  }, [entity.id]);
  return (
    <Modal title={"Tarifas · " + entity.name} onClose={onClose}>
      {error && <p className="error">{error}</p>}
      {data && (
        <Form
          onCancel={onClose}
          onSubmit={async () => {
            await api(`/entities/${entity.id}/land-prices`, {
              method: "PUT",
              body: {
                ...data,
                price_m2: data.price_m2 || null,
                price_v2: data.price_v2 || null,
              },
            });
            notify("Tarifas guardadas para " + entity.name);
            onClose();
          }}
        >
          <p className="info-box">
            Estas tarifas se aplican únicamente a los lotes de esta
            lotificadora. Los contratos existentes conservan su precio.
          </p>
          <Select
            title="Moneda de las tarifas"
            options={["HNL", "USD"]}
            value={data.currency}
            onChange={(e) => setData({ ...data, currency: e.target.value })}
          />
          <Input
            title="Precio por metro cuadrado (m²)"
            type="number"
            min="0.0001"
            step="0.0001"
            value={data.price_m2}
            onChange={(e) => setData({ ...data, price_m2: e.target.value })}
          />
          <Input
            title="Precio por vara cuadrada (vara²)"
            type="number"
            min="0.0001"
            step="0.0001"
            value={data.price_v2}
            onChange={(e) => setData({ ...data, price_v2: e.target.value })}
          />
        </Form>
      )}
    </Modal>
  );
}

export function ContractClosing({ account, onClose, onSaved }) {
  const [status, setStatus] = useState(account.closing_status),
    [reason, setReason] = useState("");
  return (
    <Modal title="Estado de cancelación y escritura" onClose={onClose}>
      <Form
        onCancel={onClose}
        confirm
        onSubmit={async () => {
          await api(`/contracts/${account.id}/closing-status`, {
            method: "PUT",
            body: { status, reason },
          });
          onSaved();
        }}
      >
        <p className="info-box">
          Pendiente de cancelar se determina por el saldo. Para marcar cancelado
          o escrituración el saldo debe ser cero. Anular un contrato es una
          operación distinta.
        </p>
        <Select
          title="Estado"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[
            { value: "paid", label: "Cancelado (pagado)" },
            { value: "pending_deed", label: "Pendiente de escriturar" },
            { value: "deeded", label: "Escriturado" },
          ]}
        />
        <Input
          title="Motivo"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          required
          minLength={3}
          maxLength={2000}
        />
      </Form>
    </Modal>
  );
}

export function PaymentDetails({ record, onClose, refresh, notify }) {
  const [data, setData] = useState({
    payment_date: record.payment_date,
    method: record.method,
    bank_reference: record.bank_reference || "",
    notes: record.notes || "",
    reason: "",
  });
  const change = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  return (
    <Modal title={"Modificar cobro · " + record.folio} onClose={onClose}>
      <Form
        onCancel={onClose}
        confirm
        onSubmit={async () => {
          await api(`/payments/${record.id}`, { method: "PUT", body: data });
          onClose();
          refresh();
          notify(
            "Cobro actualizado; el recibo se regenerará con los datos corregidos",
          );
        }}
      >
        <p className="info-box">
          Importe: {money(record.received, record.received_currency)}. Para
          corregir el importe o el contrato, anula este cobro y registra el
          correcto; se conservará su historial.
        </p>
        <Input
          title="Fecha del pago"
          type="date"
          required
          value={data.payment_date}
          onChange={(e) => change("payment_date", e.target.value)}
        />
        <Select
          title="Forma de pago"
          options={[
            { value: "cash", label: "Efectivo" },
            { value: "deposit", label: "Depósito" },
            { value: "transfer", label: "Transferencia" },
          ]}
          value={data.method}
          onChange={(e) => change("method", e.target.value)}
        />
        <Input
          title="Referencia bancaria"
          required={data.method !== "cash"}
          value={data.bank_reference}
          onChange={(e) => change("bank_reference", e.target.value)}
        />
        <Input
          title="Observaciones"
          value={data.notes}
          onChange={(e) => change("notes", e.target.value)}
        />
        <Input
          title="Motivo de la corrección"
          required
          minLength={3}
          value={data.reason}
          onChange={(e) => change("reason", e.target.value)}
        />
      </Form>
    </Modal>
  );
}

export function RequestReason({ record, onClose, refresh, notify }) {
  const [reason, setReason] = useState(record.reason);
  return (
    <Modal
      title={"Modificar motivo · Solicitud #" + record.id}
      onClose={onClose}
    >
      <Form
        onCancel={onClose}
        onSubmit={async () => {
          await api(`/approvals/${record.id}`, {
            method: "PUT",
            body: { reason },
          });
          onClose();
          refresh();
          notify("Motivo actualizado");
        }}
      >
        <Input
          title="Motivo"
          required
          minLength={3}
          maxLength={2000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Form>
    </Modal>
  );
}
