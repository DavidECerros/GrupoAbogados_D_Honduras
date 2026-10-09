let csrf = "";
export function setCsrf(value) {
  csrf = value;
}
export async function api(
  path,
  {
    method = "GET",
    body,
    headers = {},
    passive = false,
    signal,
    suppressExpiry = false,
  } = {},
) {
  const form = body instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    signal,
    headers: {
      ...(body && !form ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
      ...(passive ? { "X-Passive-Request": "1" } : {}),
      ...headers,
    },
    body: body ? (form ? body : JSON.stringify(body)) : undefined,
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    if (response.status === 401 && path !== "/auth/login" && !suppressExpiry)
      window.dispatchEvent(new Event("session-expired"));
    const detail = Array.isArray(result.detail)
      ? result.detail.map((x) => x.msg).join("; ")
      : result.detail;
    throw new Error(detail || "No fue posible completar la operación");
  }
  return response.json();
}
export const money = (value = 0, currency = "HNL") =>
  new Intl.NumberFormat("es-HN", {
    style: "currency",
    currency,
    currencyDisplay: "code",
  }).format(value / 100);
export const labels = {
  available: "Disponible",
  reserved: "Reservado",
  sold: "Vendido",
  active: "Activo",
  archived: "Archivado",
  valid: "Confirmado",
  void: "Anulado",
  pending: "Pendiente",
  issued: "Emitido",
  approved: "Aprobada",
  rejected: "Rechazada",
  released: "Liberada",
  converted: "Convertida",
  cash: "Efectivo",
  deposit: "Depósito",
  transfer: "Transferencia",
  operator: "Operador",
  superuser: "Superusuario",
  void_payment: "Anular pago",
  release_reservation: "Liberar reserva",
  transfer_contract: "Ceder contrato",
  amend_contract: "Modificar contrato",
  create_client: "Cliente creado",
  create_lot: "Lote creado",
  create_sale: "Venta creada",
  create_payment: "Pago registrado",
  update_client: "Cliente actualizado",
  download_receipt: "Recibo descargado",
  request_approval: "Autorización solicitada",
  resolve_approval: "Autorización resuelta",
  success: "Correcto",
  denied: "Denegado",
  login: "Inicio de sesión",
  logout: "Cierre de sesión",
  update_user: "Usuario actualizado",
  update_entity: "Entidad actualizada",
  create_entity: "Entidad creada",
  create_reservation: "Reserva creada",
  export_global: "Reporte exportado",
  export_own_payments: "Pagos propios exportados",
  regenerate_receipt: "Recibo regenerado",
  update_settings: "Configuración actualizada",
  daily_backup: "Respaldo diario",
  manual_backup: "Respaldo manual",
  restore: "Restauración",
  reset_password: "Contraseña restablecida",
  change_password: "Contraseña cambiada",
  create_user: "Usuario creado",
  update_lot: "Lote actualizado",
  setup: "Configuración inicial",
  login_failed: "Acceso fallido",
  download_backup: "Respaldo descargado",
};
export const label = (value) => labels[value] || value;
