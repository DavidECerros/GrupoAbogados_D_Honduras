import { useState } from "react";
import { Download, FileCheck, Landmark, Wallet } from "lucide-react";
import { api, label, money } from "./api";
import { Details } from "./details";
import {
  Badge,
  Empty,
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

export function Dashboard({ entity, today, version }) {
  const [month, setMonth] = useState(today.slice(0, 7));
  const data = useList(
    `/dashboard?month=${month}${entity ? "&entity=" + entity : ""}`,
    version,
  );
  const currencies = ["HNL", "USD"];
  return (
    <>
      <div className="toolbar">
        <p>
          Visión de{" "}
          {entity ? "la lotificadora seleccionada" : "todas las lotificadoras"}
        </p>
        <div className="row-actions">
          <Input
            title="Mes de recaudación"
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
          <a
            className="secondary"
            href={`/api/export.xlsx?month=${month}${entity ? "&entity=" + entity : ""}`}
          >
            <Download size={16} /> Exportar Excel
          </a>
        </div>
      </div>
      {data.error && <p className="error">{data.error}</p>}
      <div className="metrics">
        {currencies.map((currency) => (
          <div className="metric" key={currency}>
            <span>
              <Wallet size={17} /> Recaudación neta · {currency}
            </span>
            <strong>
              {money(
                data.collection?.find((r) => r.currency === currency)?.amount ||
                  0,
                currency,
              )}
            </strong>
            <small>Pagos del mes, excluyendo anulados</small>
          </div>
        ))}
        <div className="metric">
          <span>
            <Landmark size={17} /> Lotes disponibles
          </span>
          <strong>{data.lots?.available || 0}</strong>
          <small>{data.lots?.reserved || 0} reservados</small>
        </div>
        <div className="metric">
          <span>
            <FileCheck size={17} /> Lotes vendidos
          </span>
          <strong>{data.lots?.sold || 0}</strong>
          <small>Contratos registrados</small>
        </div>
      </div>
      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="panel-title">
            <h3>Ingresos de los últimos 6 meses</h3>
            <span className="muted">Importes recibidos</span>
          </div>
          {currencies.map((currency) => {
            const maximum = Math.max(
              1,
              ...(data.chart || []).map((r) => r[currency]),
            );
            return (
              <div className="chart" key={currency}>
                <h4>{currency}</h4>
                {(data.chart || []).map((r) => (
                  <div className="chart-row" key={r.month}>
                    <span>{r.month}</span>
                    <div className="bar-track">
                      <div
                        className={"bar " + currency}
                        style={{ width: (r[currency] / maximum) * 100 + "%" }}
                      />
                    </div>
                    <small>{money(r[currency], currency)}</small>
                  </div>
                ))}
              </div>
            );
          })}
        </section>
        <section className="panel">
          <div className="panel-title">
            <h3>Mayor deuda vencida</h3>
            <span className="muted">Por cliente y moneda</span>
          </div>
          {currencies.map((currency) => (
            <div className="debtor-list" key={currency}>
              <h4>{currency}</h4>
              {!data.top_debtors?.[currency]?.length ? (
                <p className="muted">Sin deuda vencida en esta moneda.</p>
              ) : (
                data.top_debtors[currency].map((r, i) => (
                  <div className="debtor" key={i}>
                    <span className="rank">{i + 1}</span>
                    <div>
                      <strong>{r.client}</strong>
                      <small className="block">{r.entity}</small>
                    </div>
                    <b>{money(r.overdue, currency)}</b>
                  </div>
                ))
              )}
            </div>
          ))}
        </section>
      </div>
      <p className="footnote">
        Las monedas se muestran por separado. Los pagos conservan la tasa
        registrada al momento del cobro.
      </p>
    </>
  );
}

export function Arrears({ entity, version, onCollect }) {
  const [page, setPage] = useState(1),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [q, setQ] = useState("");
  const data = useList(
    `/entities/${entity}/arrears?page=${page}&q=${encodeURIComponent(q)}${from ? "&due_from=" + from : ""}${to ? "&due_to=" + to : ""}`,
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
        <div className="filter-group">
          <Input
            title="Vencimiento desde"
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
          <Input
            title="Hasta"
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>
      <div className="metrics two">
        {["HNL", "USD"].map((currency) => (
          <div className="metric" key={currency}>
            <span>Deuda vencida · {currency}</span>
            <strong>
              {money(data.overdue_totals?.[currency] || 0, currency)}
            </strong>
            <small>Saldo total y deuda vencida son importes diferentes</small>
          </div>
        ))}
      </div>
      {data.error && <p className="error">{data.error}</p>}
      <div className="panel">
        <Table
          rows={data.items}
          busy={data.busy}
          columns={[
            { key: "client", title: "Cliente" },
            { key: "lot", title: "Lote" },
            { key: "oldest_due", title: "Obligación más antigua" },
            { key: "days_late", title: "Días de atraso" },
            {
              key: "overdue",
              title: "Deuda vencida",
              render: (r) => money(r.overdue, r.currency),
            },
            {
              key: "balance",
              title: "Saldo total",
              render: (r) => money(r.balance, r.currency),
            },
            {
              key: "category",
              title: "Situación",
              render: (r) => <Badge value={r.category} color={r.color} />,
            },
            {
              key: "action",
              title: "",
              render: (r) =>
                r.balance > 0 && (
                  <button
                    className="text-button"
                    onClick={() => onCollect(r.contract_id)}
                  >
                    Cobrar
                  </button>
                ),
            },
          ]}
        />
        <Pager total={data.total} page={page} onChange={setPage} />
      </div>
    </>
  );
}

export function Transactions({ entity, admin, version, notify }) {
  const [page, setPage] = useState(1),
    [since, setSince] = useState(""),
    [until, setUntil] = useState(""),
    [action, setAction] = useState(""),
    [state, setState] = useState(""),
    [userId, setUserId] = useState(""),
    [selected, setSelected] = useState(null);
  const users = useList(admin ? "/users" : null);
  const data = useList(
    `/transactions?page=${page}${entity ? "&entity=" + entity : ""}${since ? "&since=" + since : ""}${until ? "&until=" + until : ""}${action ? "&action=" + action : ""}${state ? "&state=" + state : ""}${userId ? "&user_id=" + userId : ""}`,
    version,
  );
  function filter(setter, value) {
    setter(value);
    setPage(1);
  }
  return (
    <>
      <div className="toolbar">
        <div className="filter-group">
          <Input
            title="Desde"
            type="date"
            value={since}
            onChange={(e) => filter(setSince, e.target.value)}
          />
          <Input
            title="Hasta"
            type="date"
            value={until}
            onChange={(e) => filter(setUntil, e.target.value)}
          />
          <Select
            title="Acción"
            value={action}
            options={[
              { value: "", label: "Todas" },
              "create_payment",
              "create_sale",
              "create_client",
              "void_payment",
              "request_approval",
              "resolve_approval",
              "update_client",
              "transfer_contract",
              "download_receipt",
              "export_global",
              "export_own_payments",
              "login",
              "login_failed",
              "logout",
              "manual_backup",
              "restore",
            ]}
            onChange={(e) => filter(setAction, e.target.value)}
          />
          <Select
            title="Resultado"
            value={state}
            options={[{ value: "", label: "Todos" }, "success", "denied"]}
            onChange={(e) => filter(setState, e.target.value)}
          />
          {admin && (
            <Select
              title="Responsable"
              value={userId}
              options={[
                { value: "", label: "Todos" },
                ...users.items.map((r) => ({
                  value: r.id,
                  label: r.full_name,
                })),
              ]}
              onChange={(e) => filter(setUserId, e.target.value)}
            />
          )}
        </div>
      </div>
      {data.error && <p className="error">{data.error}</p>}
      {!!data.payment_totals?.length && (
        <div className="totals-strip">
          {data.payment_totals.map((r, i) => (
            <span key={i}>
              {r.operator}: <strong>{money(r.amount, r.currency)}</strong>
            </span>
          ))}
        </div>
      )}
      <div className="panel">
        <Table
          rows={data.items}
          busy={data.busy}
          onRow={admin ? setSelected : undefined}
          columns={[
            {
              key: "created_at",
              title: "Fecha",
              render: (r) => new Date(r.created_at).toLocaleString("es-HN"),
            },
            { key: "operator", title: "Responsable" },
            { key: "entity", title: "Lotificadora" },
            {
              key: "action",
              title: "Operación",
              render: (r) => label(r.action),
            },
            { key: "record_id", title: "Registro" },
            {
              key: "result",
              title: "Resultado",
              render: (r) => <Badge value={r.result} />,
            },
            { key: "reason", title: "Motivo" },
          ]}
        />
        <Pager total={data.total} page={page} onChange={setPage} />
      </div>
      {selected && (
        <Modal
          title={"Evento #" + selected.id}
          onClose={() => setSelected(null)}
        >
          <p>
            {label(selected.action)} · {selected.operator} ·{" "}
            {selected.entity || "Instalación"}
          </p>
          {["before_json", "after_json"].map((key) => (
            <div key={key}>
              <h3>{key === "before_json" ? "Antes" : "Después"}</h3>
              <Details
                data={selected[key] ? JSON.parse(selected[key]) : null}
              />
            </div>
          ))}
        </Modal>
      )}
    </>
  );
}

export function Approvals({ entity, admin, version, refresh, notify }) {
  const [page, setPage] = useState(1),
    [selected, setSelected] = useState(null),
    [approve, setApprove] = useState(true),
    [reason, setReason] = useState("");
  const data = useList(
    `/approvals?page=${page}${entity ? "&entity=" + entity : ""}`,
    version,
  );
  return (
    <>
      <div className="toolbar">
        <p>
          {admin
            ? "Revisa las solicitudes antes de autorizar cambios financieros."
            : "Consulta las solicitudes que has enviado."}
        </p>
      </div>
      {data.error && <p className="error">{data.error}</p>}
      <div className="panel">
        <Table
          rows={data.items}
          busy={data.busy}
          columns={[
            { key: "id", title: "Solicitud", render: (r) => "#" + r.id },
            { key: "action", title: "Acción", render: (r) => label(r.action) },
            { key: "record_id", title: "Registro" },
            { key: "requester", title: "Solicitante" },
            { key: "reason", title: "Motivo" },
            {
              key: "status",
              title: "Estado",
              render: (r) => <Badge value={r.status} />,
            },
            { key: "resolution", title: "Resolución" },
            {
              key: "actions",
              title: "",
              render: (r) =>
                admin &&
                r.status === "pending" && (
                  <button
                    className="text-button"
                    onClick={() => {
                      setSelected(r);
                      setReason("");
                      setApprove(true);
                    }}
                  >
                    Revisar
                  </button>
                ),
            },
          ]}
        />
        <Pager total={data.total} page={page} onChange={setPage} />
      </div>
      {selected && (
        <Modal
          title={"Resolver solicitud #" + selected.id}
          onClose={() => setSelected(null)}
        >
          <p>
            <strong>{label(selected.action)}</strong> · Registro #
            {selected.record_id}
          </p>
          <p>{selected.reason}</p>
          {selected.payload !== "{}" && (
            <Details data={JSON.parse(selected.payload)} cents={false} />
          )}
          <Form
            confirm
            onCancel={() => setSelected(null)}
            onSubmit={async () => {
              await api(`/approvals/${selected.id}/resolve`, {
                method: "POST",
                body: { approve, reason },
              });
              setSelected(null);
              refresh();
              notify(approve ? "Solicitud aprobada" : "Solicitud rechazada");
            }}
          >
            <Select
              title="Decisión"
              value={approve ? "yes" : "no"}
              options={[
                { value: "yes", label: "Aprobar y ejecutar" },
                { value: "no", label: "Rechazar" },
              ]}
              onChange={(e) => setApprove(e.target.value === "yes")}
            />
            <Field title="Motivo de resolución">
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
