import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  Bell,
  Building2,
  CalendarDays,
  ChartNoAxesCombined,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  FileCheck2,
  FileText,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  RefreshCw,
  Scale,
  Search,
  Settings2,
  ShieldCheck,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { api, setCsrf } from "./api";
import { Empty, Form, Input, Modal } from "./components";
import { Catalog, Users as UserScreen } from "./catalogs";
import { Contracts, Reservations } from "./contracts";
import { Payments } from "./payments";
import { Approvals, Arrears, Dashboard, Transactions } from "./reports";
import { Settings } from "./settings";
import "./style.css";

const pages = {
  dashboard: [
    "Resumen",
    "Las cifras de tu operación, en un solo lugar.",
    LayoutDashboard,
  ],
  clients: [
    "Clientes",
    "Personas y datos de contacto de cada lotificadora.",
    Users,
  ],
  lots: ["Lotes", "Disponibilidad, ubicación y precios base.", Landmark],
  reservations: [
    "Reservas",
    "Compromisos vigentes y vencimientos por revisar.",
    CalendarDays,
  ],
  contracts: ["Contratos", "Ventas, cuotas y estados de cuenta.", FileText],
  payments: [
    "Cobros y recibos",
    "Registra pagos y consulta tus comprobantes.",
    Wallet,
  ],
  arrears: [
    "Morosidad",
    "Vencimientos, deuda vencida y saldos pendientes.",
    ChartNoAxesCombined,
  ],
  transactions: [
    "Mis transacciones",
    "Historial de operaciones y sus responsables.",
    ClipboardList,
  ],
  approvals: [
    "Autorizaciones",
    "Solicitudes de cambios y su resolución.",
    FileCheck2,
  ],
  entities: [
    "Lotificadoras",
    "Administra las entidades de esta instalación.",
    Building2,
  ],
  users: ["Usuarios", "Accesos y permisos por lotificadora.", ShieldCheck],
  settings: [
    "Configuración",
    "Tasa de cambio, recibos y respaldos.",
    Settings2,
  ],
};

function App() {
  const [status, setStatus] = useState(null),
    [session, setSession] = useState(null),
    [error, setError] = useState(""),
    [entities, setEntities] = useState([]),
    [entity, setEntity] = useState(""),
    [screen, setScreen] = useState("contracts"),
    [version, setVersion] = useState(0),
    [today, setToday] = useState(""),
    [toast, setToast] = useState(null),
    [mobileMenu, setMobileMenu] = useState(false),
    [password, setPassword] = useState(false),
    [alerts, setAlerts] = useState([]),
    [contract, setContract] = useState(null),
    [help, setHelp] = useState(false);
  const toastTimer = useRef(null),
    lastActivity = useRef(0);
  const admin = session?.role === "superuser";
  function notify(text, error = false) {
    setToast({ text, error });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 6500);
  }
  function logoutLocal() {
    setSession(null);
    setCsrf("");
    setEntities([]);
    setPassword(false);
  }
  function adopt(data) {
    setSession(data.user);
    setCsrf(data.csrf);
    if (data.today) setToday(data.today);
    setScreen(data.user.role === "superuser" ? "dashboard" : "contracts");
    setPassword(!!data.user.must_change);
  }
  useEffect(() => {
    api("/status")
      .then(setStatus)
      .catch((err) => setError(err.message));
    api("/auth/me", { passive: true, suppressExpiry: true })
      .then(adopt)
      .catch(() => {});
    const expired = () => {
      logoutLocal();
      notify("La sesión venció. Inicia sesión nuevamente.", true);
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (!session || session.must_change) return;
    const abort = new AbortController();
    api("/entities", { signal: abort.signal })
      .then((result) => {
        setEntities(result);
        setEntity((current) =>
          current && result.some((e) => String(e.id) === String(current))
            ? current
            : result[0]
              ? String(result[0].id)
              : "",
        );
      })
      .catch((err) => {
        if (err.name !== "AbortError") notify(err.message, true);
      });
    return () => abort.abort();
  }, [session?.id, session?.must_change, version]);
  useEffect(() => {
    if (!session || session.must_change) return;
    api("/alerts", { passive: true })
      .then((data) => {
        setAlerts(data.items);
        setToday(data.today);
      })
      .catch((err) => notify(err.message, true));
  }, [session?.id, session?.must_change, version]);
  useEffect(() => {
    if (!session) return;
    const keepAlive = () => {
      if (Date.now() - lastActivity.current > 60000) {
        lastActivity.current = Date.now();
        api("/auth/me").catch(() => {});
      }
    };
    const interval = setInterval(() => {
      api("/auth/me", { passive: true })
        .then((data) => {
          if (data.today !== today) {
            setToday(data.today);
            setVersion((v) => v + 1);
          }
        })
        .catch(() => {});
    }, 60000);
    window.addEventListener("pointerdown", keepAlive);
    window.addEventListener("keydown", keepAlive);
    return () => {
      clearInterval(interval);
      window.removeEventListener("pointerdown", keepAlive);
      window.removeEventListener("keydown", keepAlive);
    };
  }, [session?.id, today]);
  const refresh = () => setVersion((v) => v + 1);
  function navigate(key) {
    if (
      [
        "clients",
        "lots",
        "reservations",
        "contracts",
        "payments",
        "arrears",
      ].includes(key) &&
      !entity &&
      entities[0]
    )
      setEntity(String(entities[0].id));
    setScreen(key);
    setMobileMenu(false);
    setContract(null);
  }
  function collect(id) {
    setContract(id);
    setScreen("payments");
  }
  if (!status)
    return (
      <div className="startup">
        <Scale size={38} />
        <p>{error || "Conectando con la instalación local…"}</p>
        {error && (
          <button className="primary" onClick={() => location.reload()}>
            Reintentar
          </button>
        )}
      </div>
    );
  if (!session)
    return (
      <>
        <Auth
          initialized={status.initialized}
          onSetup={() => {
            setStatus({ ...status, initialized: true });
            notify("Superusuario creado. Inicia sesión.");
          }}
          onLogin={async (data) => {
            adopt(data);
            const result = await api("/auth/me");
            setToday(result.today);
          }}
        />
        {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
      </>
    );
  const common = {
    entity: Number(entity),
    today,
    admin,
    version,
    refresh,
    notify,
  };
  const requiresEntity = [
    "clients",
    "lots",
    "reservations",
    "contracts",
    "payments",
    "arrears",
  ].includes(screen);
  const navigation = [
    "dashboard",
    "clients",
    "lots",
    "reservations",
    "contracts",
    "payments",
    "arrears",
    "transactions",
    "approvals",
  ];
  const selected = entities.find((e) => String(e.id) === String(entity));
  const visibleAlerts = alerts.filter(
    (r) => !entity || String(r.entity_id) === String(entity),
  );
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobileMenu ? "open" : "")}>
        <div className="brand">
          <div className="brand-mark">
            <Scale size={25} />
          </div>
          <div>
            <strong>GRUPO ABOGADOS</strong>
            <span>D HONDURAS</span>
          </div>
          <button
            className="icon mobile-close"
            onClick={() => setMobileMenu(false)}
            aria-label="Cerrar navegación"
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace-label">ADMINISTRACIÓN DE LOTES</div>
        <nav>
          {navigation
            .filter((key) => admin || key !== "dashboard")
            .map((key) => {
              const Icon = pages[key][2];
              return (
                <button
                  key={key}
                  className={screen === key ? "active" : ""}
                  onClick={() => navigate(key)}
                >
                  <Icon size={19} />
                  <span>
                    {key === "transactions" && admin
                      ? "Historial global"
                      : pages[key][0]}
                  </span>
                  {key === "arrears" &&
                    visibleAlerts.some((r) => r.overdue_count > 0) && (
                      <span className="nav-dot" />
                    )}
                </button>
              );
            })}
          {admin && (
            <>
              <span className="nav-section">ADMINISTRACIÓN</span>
              {["entities", "users", "settings"].map((key) => {
                const Icon = pages[key][2];
                return (
                  <button
                    key={key}
                    className={screen === key ? "active" : ""}
                    onClick={() => navigate(key)}
                  >
                    <Icon size={19} />
                    <span>{pages[key][0]}</span>
                  </button>
                );
              })}
            </>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-status">
            <span /> Instalación local
          </div>
          <button className="help-link" onClick={() => setHelp(true)}>
            <CircleHelp size={16} /> Ayuda y operación
          </button>
          <div className="profile">
            <span className="avatar">
              {session.full_name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{session.full_name}</strong>
              <small>{admin ? "Superusuario" : "Operador"}</small>
            </div>
            <button
              className="icon"
              aria-label="Cerrar sesión"
              onClick={async () => {
                try {
                  await api("/auth/logout", { method: "POST" });
                  logoutLocal();
                } catch (err) {
                  notify(err.message, true);
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="mobile-backdrop"
          aria-label="Cerrar menú"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <div className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon menu-toggle"
              aria-label="Abrir navegación"
              onClick={() => setMobileMenu(true)}
            >
              <Menu size={22} />
            </button>
            <Building2 size={18} />
            <select
              aria-label="Lotificadora seleccionada"
              value={entity}
              onChange={(e) => {
                setEntity(e.target.value);
                refresh();
              }}
            >
              {admin && !requiresEntity && (
                <option value="">Todas las lotificadoras</option>
              )}
              {entities.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                  {e.status === "archived" ? " · archivada" : ""}
                </option>
              ))}
            </select>
            {!entities.length && <span>Sin lotificadoras asignadas</span>}
          </div>
          <div className="topbar-right">
            <span className="date">
              {today
                ? new Date(today + "T12:00:00").toLocaleDateString("es-HN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })
                : ""}
            </span>
            <button
              className="icon"
              aria-label="Cambiar contraseña"
              title="Cambiar contraseña"
              onClick={() => setPassword(true)}
            >
              <ShieldCheck size={19} />
            </button>
            <button
              className="icon"
              aria-label="Actualizar datos"
              onClick={refresh}
            >
              <RefreshCw size={18} />
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {selected?.name || "GRUPO ABOGADOS D HONDURAS"}
              </span>
              <h1>
                {screen === "transactions" && admin
                  ? "Historial global"
                  : pages[screen][0]}
              </h1>
              <p>{pages[screen][1]}</p>
            </div>
            <div className="offline-chip">
              <span /> Disponible sin internet
            </div>
          </div>
          {visibleAlerts.some(
            (r) =>
              r.overdue_count > 0 ||
              r.expired_reservations > 0 ||
              r.upcoming_count > 0,
          ) && (
            <div className="alert-banner">
              <Bell size={18} />
              <span>
                {visibleAlerts.reduce((sum, r) => sum + r.overdue_count, 0)}{" "}
                contratos con vencimientos pendientes ·{" "}
                {visibleAlerts.reduce((sum, r) => sum + r.upcoming_count, 0)}{" "}
                próximos ·{" "}
                {visibleAlerts.reduce(
                  (sum, r) => sum + r.expired_reservations,
                  0,
                )}{" "}
                reservas vencidas
              </span>
              <button
                className="text-button"
                onClick={() => {
                  if (!entity && alerts[0])
                    setEntity(String(alerts[0].entity_id));
                  navigate("arrears");
                }}
              >
                Revisar <ArrowUpRight size={15} />
              </button>
            </div>
          )}
          {requiresEntity && !entity ? (
            <div className="panel">
              <Empty>
                {admin
                  ? "Crea una lotificadora para comenzar a registrar clientes y lotes."
                  : "Solicita al superusuario que te asigne una lotificadora."}
              </Empty>
              {admin && (
                <div className="empty-action">
                  <button
                    className="primary"
                    onClick={() => navigate("entities")}
                  >
                    Administrar lotificadoras
                  </button>
                </div>
              )}
            </div>
          ) : (
            <React.Fragment key={screen + "-" + entity}>
              {screen === "dashboard" && <Dashboard {...common} />}
              {["clients", "lots", "entities"].includes(screen) && (
                <Catalog {...common} kind={screen} />
              )}
              {screen === "users" && (
                <UserScreen {...common} entities={entities} />
              )}
              {screen === "contracts" && (
                <Contracts {...common} onCollect={collect} />
              )}
              {screen === "reservations" && <Reservations {...common} />}
              {screen === "payments" && (
                <Payments
                  {...common}
                  selectedContract={contract}
                  clearSelected={() => setContract(null)}
                />
              )}
              {screen === "arrears" && (
                <Arrears {...common} onCollect={collect} />
              )}
              {screen === "transactions" && <Transactions {...common} />}
              {screen === "approvals" && <Approvals {...common} />}
              {screen === "settings" && (
                <Settings {...common} onRestored={logoutLocal} />
              )}
            </React.Fragment>
          )}
        </main>
        <footer>
          Grupo Abogados D Honduras{" "}
          <span>Gestión de lotificadoras · v0.1.1</span>
        </footer>
      </div>
      {password && (
        <PasswordChange
          forced={!!session.must_change}
          onClose={() => setPassword(false)}
          onSaved={async () => {
            const result = await api("/auth/me");
            setSession(result.user);
            setPassword(false);
            refresh();
            notify("Contraseña actualizada");
          }}
        />
      )}
      {help && (
        <Modal title="Ayuda de operación" onClose={() => setHelp(false)}>
          <p>
            Crea una lotificadora, registra clientes y lotes, y después una
            venta. El contrato genera prima y cuotas pendientes.
          </p>
          <p>
            Registra cada cobro en «Cobros y recibos». Revisa el saldo y
            confirma los datos. Descarga el recibo para imprimirlo desde tu
            navegador.
          </p>
          <p>
            Los operadores solicitan cambios; el superusuario los revisa en
            «Autorizaciones». Los movimientos quedan en el historial.
          </p>
          <p>
            Consulta «Morosidad» al comenzar el día. El rojo indica deuda
            vencida; el amarillo indica vencimientos de hoy a cuatro días.
          </p>
          <p>
            En «Configuración», el superusuario puede guardar respaldos y
            restaurarlos con las demás sesiones cerradas. Los datos permanecen
            en el equipo principal.
          </p>
        </Modal>
      )}
      {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

function Toast({ toast, onClose }) {
  return (
    <div
      className={"toast " + (toast.error ? "error-toast" : "")}
      role="status"
    >
      <CheckCircle2 size={18} />
      <span>{toast.text}</span>
      <button className="icon" aria-label="Cerrar aviso" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}
function Auth({ initialized, onLogin, onSetup }) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [name, setName] = useState("");
  return (
    <div className="auth-shell">
      <section className="auth-art">
        <div className="brand">
          <div className="brand-mark">
            <Scale size={30} />
          </div>
          <div>
            <strong>GRUPO ABOGADOS</strong>
            <span>D HONDURAS</span>
          </div>
        </div>
        <div className="auth-message">
          <span className="eyebrow">CONTROL Y CONFIANZA</span>
          <h1>
            Cada lote.
            <br />
            Cada cliente.
            <br />
            <em>Cada movimiento.</em>
          </h1>
          <p>
            La administración de tus lotificadoras, con el respaldo de un
            registro claro.
          </p>
          <div className="auth-lines">
            <span />
            <span />
            <span />
          </div>
        </div>
        <small>Gestión local · Tus datos permanecen en tu equipo</small>
      </section>
      <section className="auth-form">
        <div className="auth-form-inner">
          <span className="eyebrow">
            {initialized ? "BIENVENIDO" : "PRIMER INICIO"}
          </span>
          <h2>{initialized ? "Inicia sesión" : "Configura tu instalación"}</h2>
          <p>
            {initialized
              ? "Accede con tu usuario para continuar."
              : "Crea el único superusuario de esta instalación. No hay credenciales predeterminadas."}
          </p>
          <Form
            submit={initialized ? "Ingresar al sistema" : "Crear superusuario"}
            onSubmit={async () => {
              if (initialized)
                await onLogin(
                  await api("/auth/login", {
                    method: "POST",
                    body: { username, password },
                  }),
                );
              else {
                await api("/setup", {
                  method: "POST",
                  body: { username, password, full_name: name },
                });
                setPassword("");
                onSetup();
              }
            }}
          >
            {!initialized && (
              <Input
                title="Nombre completo"
                required
                maxLength={150}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
            <Input
              title="Nombre de usuario"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
            <Input
              title="Contraseña"
              type="password"
              required
              minLength={initialized ? 1 : 12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={initialized ? "current-password" : "new-password"}
              hint={!initialized ? "Al menos 12 caracteres." : ""}
            />
          </Form>
          <div className="auth-local">
            <ShieldCheck size={16} /> Acceso seguro a la instalación local
          </div>
        </div>
      </section>
    </div>
  );
}
function PasswordChange({ forced, onClose, onSaved }) {
  const [current, setCurrent] = useState(""),
    [next, setNext] = useState(""),
    [repeat, setRepeat] = useState("");
  return (
    <Modal
      title={
        forced ? "Cambia tu contraseña para continuar" : "Cambiar contraseña"
      }
      onClose={forced ? () => {} : onClose}
    >
      <Form
        onCancel={forced ? undefined : onClose}
        onSubmit={async () => {
          if (next !== repeat) throw new Error("Las contraseñas no coinciden");
          await api("/auth/password", {
            method: "POST",
            body: { current_password: current, new_password: next },
          });
          await onSaved();
        }}
      >
        <Input
          title="Contraseña actual"
          type="password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
        />
        <Input
          title="Nueva contraseña"
          type="password"
          required
          minLength={12}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
        />
        <Input
          title="Repite la nueva contraseña"
          type="password"
          required
          minLength={12}
          value={repeat}
          onChange={(e) => setRepeat(e.target.value)}
          autoComplete="new-password"
        />
      </Form>
    </Modal>
  );
}

createRoot(document.getElementById("root")).render(<App />);
