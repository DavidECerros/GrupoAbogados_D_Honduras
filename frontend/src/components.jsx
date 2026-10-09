import { useEffect, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  Search,
  X,
} from "lucide-react";
import { api, label } from "./api";

export function Badge({ value, color }) {
  return (
    <span className={"badge " + (color || value || "")}>{label(value)}</span>
  );
}
export function Empty({
  children = "Aún no hay registros. Crea el primero para comenzar.",
}) {
  return (
    <div className="empty">
      <span>—</span>
      <p>{children}</p>
    </div>
  );
}
export function Field({ title, children, hint }) {
  return (
    <label className="field">
      <span>{title}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Input({ title, hint, ...props }) {
  return (
    <Field title={title} hint={hint}>
      <input {...props} />
    </Field>
  );
}
export function Select({ title, options, ...props }) {
  return (
    <Field title={title}>
      <select {...props}>
        {options.map((option) => (
          <option key={option.value ?? option} value={option.value ?? option}>
            {option.label ?? label(option)}
          </option>
        ))}
      </select>
    </Field>
  );
}
export function Table({ columns, rows, busy, onRow }) {
  return (
    <div className="table-wrap">
      {busy ? (
        <div className="loading">
          <LoaderCircle className="spin" /> Cargando…
        </div>
      ) : !rows.length ? (
        <Empty />
      ) : (
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.title}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id ?? row.contract_id}
                onClick={onRow ? () => onRow(row) : undefined}
                className={onRow ? "clickable" : ""}
              >
                {columns.map((column) => (
                  <td key={column.key}>
                    {column.render
                      ? column.render(row)
                      : (row[column.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
export function Pager({ total, page, onChange, size = 30 }) {
  return (
    <div className="pager">
      <small>
        {total} registros · Página {page} de{" "}
        {Math.max(1, Math.ceil(total / size))}
      </small>
      <div>
        <button
          className="icon"
          aria-label="Página anterior"
          disabled={page === 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <button
          className="icon"
          aria-label="Página siguiente"
          disabled={page * size >= total}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}
export function SearchBox({ value, onChange, placeholder = "Buscar…" }) {
  return (
    <div className="search">
      <Search size={17} />
      <input
        aria-label={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
export function Modal({ title, children, onClose, wide = false }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    const previous = document.activeElement;
    const dialog = document.querySelector("dialog");
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      window.removeEventListener("keydown", handler);
      previous?.focus?.();
    };
  }, []);
  return (
    <dialog
      className={wide ? "wide" : ""}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="modal-heading">
        <h2>{title}</h2>
        <button className="icon" aria-label="Cerrar" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Form({
  children,
  onSubmit,
  submit = "Guardar",
  onCancel,
  confirm = false,
  confirmationText = "Confirma los datos antes de registrar esta operación.",
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [accepted, setAccepted] = useState(false);
  async function send(e) {
    e.preventDefault();
    if (confirm && !accepted) return;
    setError("");
    setBusy(true);
    try {
      await onSubmit();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={send}>
      {children}
      {confirm && (
        <label className="confirmation">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
            required
          />
          {confirmationText}
        </label>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="secondary" onClick={onCancel}>
            Cancelar
          </button>
        )}
        <button className="primary" disabled={busy || (confirm && !accepted)}>
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Check size={16} />
          )}
          {submit}
        </button>
      </div>
    </form>
  );
}
export function Picker({
  title,
  entity,
  collection,
  value,
  onChange,
  predicate = () => true,
}) {
  const [q, setQ] = useState(""),
    [rows, setRows] = useState([]),
    [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    const timer = setTimeout(() => {
      api(
        `/entities/${entity}/${collection}?q=${encodeURIComponent(q)}&size=100${collection === "clients" ? "&state=active" : ""}`,
        { signal: abort.signal },
      )
        .then((data) => setRows(data.items.filter(predicate)))
        .catch((err) => {
          if (err.name !== "AbortError") setError(err.message);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [q, entity, collection]);
  return (
    <div className="picker">
      <SearchBox
        placeholder={"Buscar " + title.toLowerCase()}
        value={q}
        onChange={setQ}
      />
      <Select
        title={title}
        value={value || ""}
        required
        onChange={(e) =>
          onChange(
            Number(e.target.value),
            rows.find((r) => r.id === Number(e.target.value)),
          )
        }
        options={[
          { value: "", label: "Selecciona una opción" },
          ...rows.map((row) => ({
            value: row.id,
            label: row.name
              ? row.name + " · " + row.document
              : row.code + " · " + label(row.status),
          })),
        ]}
      />
      {error && <small className="error">{error}</small>}
    </div>
  );
}
export function useList(path, version = 0) {
  const [data, setData] = useState({ items: [], total: 0 }),
    [busy, setBusy] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    setBusy(true);
    setError("");
    if (!path) {
      setData({ items: [], total: 0 });
      setBusy(false);
      return;
    }
    const timer = setTimeout(
      () =>
        api(path, { signal: abort.signal })
          .then((result) =>
            setData(
              Array.isArray(result)
                ? { items: result, total: result.length }
                : result,
            ),
          )
          .catch((err) => {
            if (err.name !== "AbortError") setError(err.message);
          })
          .finally(() => {
            if (!abort.signal.aborted) setBusy(false);
          }),
      200,
    );
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [path, version]);
  return { ...data, busy, error };
}
