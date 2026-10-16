import { useEffect, useState } from "react";
import { Banknote, Download, Printer } from "lucide-react";
import { api, label, money } from "./api";
import { PaymentDetails } from "./record-tools";
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

export function Payments({
  entity,
  today,
  admin,
  selectedContract,
  clearSelected,
  version,
  refresh,
  notify,
}) {
  const [page, setPage] = useState(1),
    [since, setSince] = useState(""),
    [until, setUntil] = useState(""),
    [state, setState] = useState("valid"),
    [collect, setCollect] = useState(false),
    [voiding, setVoiding] = useState(null),
    [reason, setReason] = useState(""),
    [editing, setEditing] = useState(null);
  const filters = `${since ? "&since=" + since : ""}${until ? "&until=" + until : ""}&state=${state}`;
  const { items, total, busy, error } = useList(
    `/entities/${entity}/payments?page=${page}${filters}`,
    version,
  );
  useEffect(() => {
    if (selectedContract) setCollect(true);
  }, [selectedContract]);
  function closeCollect() {
    setCollect(false);
    clearSelected();
  }
  return (
    <>
      <div className="toolbar">
        <div className="filter-group">
          <Input
            title="Desde"
            type="date"
            value={since}
            onChange={(e) => {
              setSince(e.target.value);
              setPage(1);
            }}
          />
          <Input
            title="Hasta"
            type="date"
            value={until}
            onChange={(e) => {
              setUntil(e.target.value);
              setPage(1);
            }}
          />
          <Select
            title="Estado"
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setPage(1);
            }}
            options={[{ value: "", label: "Todos" }, "valid", "void"]}
          />
        </div>
        <div className="row-actions">
          <a
            className="secondary"
            href={`/api/my-payments.xlsx?entity=${entity}${since ? "&since=" + since : ""}${until ? "&until=" + until : ""}`}
          >
            <Download size={16} /> Mis pagos
          </a>
          <button className="primary" onClick={() => setCollect(true)}>
            <Banknote size={17} /> Registrar cobro
          </button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <Table
          rows={items}
          busy={busy}
          columns={[
            {
              key: "folio",
              title: "Recibo",
              render: (r) => <strong>{r.folio}</strong>,
            },
            { key: "payment_date", title: "Fecha" },
            {
              key: "months_paid",
              title: "Meses / cuotas pagados",
              render: (r) => (
                <small title={r.months_paid}>{r.months_paid || "—"}</small>
              ),
            },
            {
              key: "client",
              title: "Cliente / lote",
              render: (r) => (
                <>
                  {r.client}
                  <small className="block">Lote {r.lot}</small>
                </>
              ),
            },
            {
              key: "received",
              title: "Recibido",
              render: (r) => money(r.received, r.received_currency),
            },
            ...(admin ? [{ key: "operator", title: "Responsable" }] : []),
            {
              key: "status",
              title: "Estado",
              render: (r) => (
                <>
                  <Badge value={r.status} />
                  {r.receipt_status === "pending" && (
                    <small className="block warning">PDF pendiente</small>
                  )}
                </>
              ),
            },
            {
              key: "actions",
              title: "",
              render: (r) => (
                <div className="row-actions">
                  <a
                    className="icon"
                    aria-label={"Descargar " + r.folio}
                    href={`/api/receipts/${r.receipt_id}/pdf`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Printer size={16} />
                  </a>
                  {r.status === "valid" && (
                    <button
                      className="text-button danger-text"
                      onClick={() => {
                        setVoiding(r);
                        setReason("");
                      }}
                    >
                      {admin ? "Anular" : "Solicitar anulación"}
                    </button>
                  )}
                  {admin && r.status === "valid" && (
                    <button
                      className="text-button"
                      onClick={() => setEditing(r)}
                    >
                      Modificar
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
        <Pager total={total} page={page} onChange={setPage} />
      </div>
      {collect && (
        <Collection
          entity={entity}
          today={today}
          initialContract={selectedContract}
          onClose={closeCollect}
          refresh={refresh}
          notify={notify}
        />
      )}
      {editing && (
        <PaymentDetails
          record={editing}
          onClose={() => setEditing(null)}
          refresh={refresh}
          notify={notify}
        />
      )}
      {voiding && (
        <Modal
          title={admin ? "Anular pago" : "Solicitar anulación"}
          onClose={() => setVoiding(null)}
        >
          <Form
            onCancel={() => setVoiding(null)}
            confirm
            confirmationText="Confirmo la solicitud. La anulación conservará el pago y restituirá el saldo."
            onSubmit={async () => {
              await api(
                admin
                  ? `/payments/${voiding.id}/void`
                  : `/entities/${entity}/approvals`,
                {
                  method: "POST",
                  body: admin
                    ? { reason }
                    : { action: "void_payment", record_id: voiding.id, reason },
                },
              );
              setVoiding(null);
              refresh();
              notify(admin ? "Pago anulado" : "Solicitud enviada");
            }}
          >
            <p>
              <strong>{voiding.folio}</strong> ·{" "}
              {money(voiding.received, voiding.received_currency)} ·{" "}
              {voiding.client}
            </p>
            <Field title="Motivo">
              <textarea
                required
                minLength={3}
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

function Collection({
  entity,
  today,
  initialContract,
  onClose,
  refresh,
  notify,
}) {
  const [q, setQ] = useState(""),
    [chosen, setChosen] = useState(initialContract || ""),
    [account, setAccount] = useState(null),
    [error, setError] = useState(""),
    [rate, setRate] = useState(""),
    [preview, setPreview] = useState(null),
    [previewError, setPreviewError] = useState(""),
    [result, setResult] = useState(null);
  const { items } = useList(
    `/entities/${entity}/contracts?q=${encodeURIComponent(q)}&size=100`,
  );
  const [data, setData] = useState({
    operation_id: crypto.randomUUID(),
    amount: "",
    currency: "HNL",
    payment_date: today,
    method: "cash",
    bank_reference: "",
    notes: "",
    start_obligation_id: "",
  });
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  useEffect(() => {
    api("/exchange-rate")
      .then((r) => setRate(r.exchange_rate))
      .catch((err) => setError(err.message));
  }, []);
  useEffect(() => {
    setAccount(null);
    setError("");
    if (chosen)
      api(`/contracts/${chosen}`)
        .then((account) => {
          setAccount(account);
          setData((prev) => ({
            ...prev,
            currency: account.currency,
            start_obligation_id: "",
          }));
        })
        .catch((err) => setError(err.message));
  }, [chosen]);
  useEffect(() => {
    setPreview(null);
    setPreviewError("");
    if (!account || !data.amount || result) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api("/payments/preview", {
        method: "POST",
        signal: controller.signal,
        body: {
          operation_id: data.operation_id,
          contract_id: Number(chosen),
          amount: data.amount,
          currency: data.currency,
          start_obligation_id: data.start_obligation_id
            ? Number(data.start_obligation_id)
            : null,
        },
      })
        .then(setPreview)
        .catch((e) => {
          if (!controller.signal.aborted) setPreviewError(e.message);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    account,
    chosen,
    data.amount,
    data.currency,
    data.start_obligation_id,
    data.operation_id,
    result,
  ]);
  const crossing = account && data.currency !== account.currency;
  const applied = !crossing
    ? Number(data.amount || 0)
    : rate
      ? data.currency === "HNL"
        ? Number(data.amount || 0) / Number(rate)
        : Number(data.amount || 0) * Number(rate)
      : null;
  return (
    <Modal
      title={result ? "Cobro confirmado" : "Registrar cobro"}
      onClose={onClose}
      wide
    >
      {result ? (
        <div className="payment-success">
          <div className="success-icon">
            <Banknote size={30} />
          </div>
          <h2>{result.folio}</h2>
          <p>{money(result.received, result.received_currency)} recibidos</p>
          <p>{result.months_paid}</p>
          <p>
            Saldo posterior:{" "}
            <strong>{money(result.balance_after, account.currency)}</strong>
          </p>
          {result.receipt_warning && (
            <p className="warning info-box">{result.receipt_warning}</p>
          )}
          <div className="form-actions">
            <a
              className="primary"
              href={`/api/receipts/${result.receipt_id}/pdf`}
              target="_blank"
              rel="noreferrer"
            >
              <Printer size={17} /> Abrir e imprimir recibo
            </a>
            <button className="secondary" onClick={onClose}>
              Terminar
            </button>
          </div>
        </div>
      ) : (
        <Form
          onCancel={onClose}
          submit="Confirmar cobro"
          confirm
          confirmationText="Revisé cliente, moneda, importe y fecha. Confirmo el cobro."
          onSubmit={async () => {
            if (!account) throw new Error("Selecciona un contrato");
            if (!preview)
              throw new Error(
                previewError ||
                  "Espera la vista previa de aplicación del cobro",
              );
            const result = await api("/payments", {
              method: "POST",
              body: {
                ...data,
                contract_id: Number(chosen),
                start_obligation_id: data.start_obligation_id
                  ? Number(data.start_obligation_id)
                  : null,
                allocation_token: preview.allocation_token,
              },
            });
            setResult(result);
            refresh();
            notify("Pago confirmado · " + result.folio);
          }}
        >
          <SearchBox
            value={q}
            onChange={setQ}
            placeholder="Buscar cliente, documento o lote"
          />
          <Select
            title="Contrato a cobrar"
            required
            value={chosen}
            onChange={(e) => setChosen(Number(e.target.value))}
            options={[
              { value: "", label: "Selecciona un contrato" },
              ...(account && !items.some((r) => r.id === Number(chosen))
                ? [
                    {
                      value: account.id,
                      label:
                        "#" +
                        account.id +
                        " · " +
                        account.client.name +
                        " · Lote " +
                        account.lot.code,
                    },
                  ]
                : []),
              ...items
                .filter((r) => r.balance > 0 || r.id === Number(chosen))
                .map((r) => ({
                  value: r.id,
                  label: `#${r.id} · ${r.client} · Lote ${r.lot} · ${money(r.balance, r.currency)}`,
                })),
            ]}
          />
          {error && <p className="error">{error}</p>}
          {account && (
            <>
              <div className="account-summary">
                <div>
                  <strong>{account.client.name}</strong>
                  <p>
                    Lote {account.lot.code} · {account.client.document}
                  </p>
                </div>
                <div>
                  <small>Saldo antes del cobro</small>
                  <h2>{money(account.balance, account.currency)}</h2>
                </div>
              </div>
              <div className="obligations-strip">
                <span>
                  Prima pendiente:{" "}
                  <strong>
                    {money(
                      account.obligations[0].amount -
                        account.obligations[0].paid,
                      account.currency,
                    )}
                  </strong>
                </span>
                <span>
                  Cuotas vencidas:{" "}
                  <strong>
                    {
                      account.obligations.filter(
                        (r) =>
                          r.number > 0 &&
                          r.due_date < today &&
                          r.paid < r.amount,
                      ).length
                    }
                  </strong>
                </span>
              </div>
              <div className="form-grid">
                <Select
                  title="Mes / cuota que está pagando"
                  value={data.start_obligation_id}
                  onChange={(e) =>
                    update("start_obligation_id", e.target.value)
                  }
                  options={[
                    {
                      value: "",
                      label:
                        "Automático: prima y cuotas pendientes más antiguas",
                    },
                    ...account.obligations
                      .filter((o) => o.paid < o.amount)
                      .map((o) => ({
                        value: o.id,
                        label:
                          (o.number === 0 ? "Prima" : "Cuota " + o.number) +
                          " · " +
                          new Intl.DateTimeFormat("es-HN", {
                            month: "long",
                            year: "numeric",
                            timeZone: "UTC",
                          }).format(new Date(o.due_date + "T12:00:00Z")) +
                          " · Pendiente " +
                          money(o.amount - o.paid, account.currency),
                      })),
                  ]}
                />
                <Input
                  title="Importe recibido"
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={data.amount}
                  onChange={(e) => update("amount", e.target.value)}
                />
                <Select
                  title="Moneda recibida"
                  options={["HNL", "USD"]}
                  value={data.currency}
                  onChange={(e) => update("currency", e.target.value)}
                />
                <Input
                  title="Fecha de pago"
                  type="date"
                  required
                  max={today}
                  value={data.payment_date}
                  onChange={(e) => update("payment_date", e.target.value)}
                />
                <Select
                  title="Método de pago"
                  options={["cash", "deposit", "transfer"]}
                  value={data.method}
                  onChange={(e) => update("method", e.target.value)}
                />
                {data.method !== "cash" && (
                  <Input
                    title="Comprobante bancario"
                    required
                    value={data.bank_reference}
                    onChange={(e) => update("bank_reference", e.target.value)}
                  />
                )}
                <Input
                  title="Observaciones (opcional)"
                  value={data.notes}
                  onChange={(e) => update("notes", e.target.value)}
                />
              </div>
              <div className="info-box">
                {crossing && (
                  <p>
                    Tasa configurada:{" "}
                    {rate
                      ? `${rate} HNL por USD`
                      : "Pendiente de configurar por el superusuario"}
                  </p>
                )}
                Aplicación estimada:{" "}
                <strong>
                  {applied === null
                    ? "Tasa requerida"
                    : money(
                        Math.round((applied + Number.EPSILON) * 100),
                        account.currency,
                      )}
                </strong>
                <small className="block">
                  El cobro empieza en la cuota seleccionada y el excedente se
                  aplica a las siguientes. Un importe menor queda como abono
                  parcial. Automático empieza por la prima y la deuda más
                  antigua.
                </small>
              </div>
              {previewError && <p className="error">{previewError}</p>}
              {preview && (
                <>
                  {preview.prior_pending > 0 && (
                    <p className="info-box">
                      Las cuotas anteriores conservarán un pendiente de{" "}
                      {money(preview.prior_pending, account.currency)}.
                    </p>
                  )}
                  <h3>Aplicación del cobro por mes</h3>
                  <Table
                    rows={preview.allocations}
                    columns={[
                      { key: "label", title: "Mes / cuota" },
                      {
                        key: "amount",
                        title: "Se aplica",
                        render: (r) => money(r.amount, account.currency),
                      },
                      {
                        key: "remaining_after",
                        title: "Queda pendiente en esa cuota",
                        render: (r) =>
                          money(r.remaining_after, account.currency),
                      },
                    ]}
                  />
                </>
              )}
              <button
                type="button"
                className="secondary"
                onClick={async () => {
                  try {
                    const updated = await api(`/contracts/${chosen}`);
                    setAccount(updated);
                    setData((prev) => ({
                      ...prev,
                      start_obligation_id: updated.obligations.some(
                        (o) =>
                          String(o.id) === String(prev.start_obligation_id) &&
                          o.paid < o.amount,
                      )
                        ? prev.start_obligation_id
                        : "",
                    }));
                    notify(
                      "Cuotas actualizadas. Revisa el mes y la aplicación antes de confirmar.",
                    );
                  } catch (e) {
                    setError(e.message);
                  }
                }}
              >
                Actualizar cuotas y aplicación
              </button>
            </>
          )}
        </Form>
      )}
    </Modal>
  );
}
