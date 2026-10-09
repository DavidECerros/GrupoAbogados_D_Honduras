import { label, money } from "./api";

const names = {
  id: "ID del registro",
  name: "Nombre",
  full_name: "Nombre completo",
  username: "Usuario",
  document_type: "Tipo de documento",
  document: "Documento",
  phone: "Teléfono",
  email: "Correo",
  notes: "Observaciones",
  code: "Lote",
  description: "Ubicación",
  entity_id: "Lotificadora ID",
  client_id: "Cliente ID",
  lot_id: "Lote ID",
  contract_id: "Contrato ID",
  new_client_id: "Nuevo propietario ID",
  price: "Precio",
  down_payment: "Prima",
  installments: "Cuotas",
  down_due: "Vencimiento de prima",
  first_due: "Primer vencimiento",
  currency: "Moneda",
  received_currency: "Moneda recibida",
  received: "Recibido",
  applied: "Aplicado",
  balance: "Saldo pendiente",
  balance_after: "Saldo posterior",
  folio: "Recibo",
  status: "Estado",
  active: "Cuenta activa",
  role: "Rol",
  entity_ids: "Lotificadoras asignadas",
  effective_date: "Fecha efectiva",
  expires_on: "Vencimiento",
  month: "Mes",
  exchange_rate: "Tasa HNL por USD",
  timezone: "Zona horaria",
  paper: "Tamaño de papel",
  backup_destination: "Destino de respaldo",
  name_before: "Nombre anterior",
  approved: "Aprobado",
  number: "Cuota",
  due_date: "Vencimiento",
  amount: "Importe",
  paid: "Pagado",
  created_at: "Fecha de registro",
  created_by: "Responsable ID",
  version: "Versión",
};
const monetary = new Set([
  "price",
  "down_payment",
  "received",
  "applied",
  "balance",
  "balance_after",
  "amount",
  "paid",
]);
export function Details({ data, currency = "HNL", cents = true }) {
  if (!data || typeof data !== "object") return <p>Sin datos adicionales.</p>;
  const rows = Object.entries(data).filter(([key]) => names[key]);
  function display(key, value) {
    if (value === null || value === "") return "—";
    if (monetary.has(key))
      return money(
        cents ? Number(value) : Math.round(Number(value) * 100),
        data.currency || data.received_currency || currency,
      );
    if (Array.isArray(value)) return value.join(", ") || "Sin asignaciones";
    if (typeof value === "boolean" || key === "active")
      return value ? "Sí" : "No";
    if (key === "paper")
      return value === "half_letter" ? "Media carta" : "Carta";
    return label(String(value));
  }
  return (
    <div className="details-grid">
      {rows.length ? (
        rows.map(([key, value]) => (
          <div key={key}>
            <small>{names[key]}</small>
            <strong>{display(key, value)}</strong>
          </div>
        ))
      ) : (
        <p>Sin campos adicionales.</p>
      )}
    </div>
  );
}
