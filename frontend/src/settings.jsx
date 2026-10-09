import { useEffect, useState } from "react";
import { Archive, Download, RotateCcw, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { Form, Input, Modal, Select, Table, useList } from "./components";

export function Settings({ version, refresh, notify, onRestored }) {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [restore, setRestore] = useState(false),
    [file, setFile] = useState(null),
    [confirmation, setConfirmation] = useState("");
  const backups = useList("/backups", version);
  useEffect(() => {
    api("/settings")
      .then((result) =>
        setData({
          timezone: result.timezone,
          exchange_rate: result.exchange_rate || "",
          paper: result.paper,
          backup_destination: result.backup_destination || "",
        }),
      )
      .catch((err) => setError(err.message));
  }, []);
  const update = (key, value) => setData((prev) => ({ ...prev, [key]: value }));
  return (
    <>
      {error && <p className="error">{error}</p>}
      <div className="settings-grid">
        <section className="panel padded">
          <h3>Configuración de la instalación</h3>
          {data && (
            <Form
              onSubmit={async () => {
                await api("/settings", {
                  method: "PUT",
                  body: { ...data, exchange_rate: data.exchange_rate || null },
                });
                refresh();
                notify("Configuración guardada");
              }}
            >
              <Input
                title="Tasa de cambio · HNL por USD"
                type="number"
                min="0.000001"
                step="0.000001"
                value={data.exchange_rate}
                onChange={(e) => update("exchange_rate", e.target.value)}
                hint="Los pagos anteriores conservan su propia tasa."
              />
              <Input
                title="Zona horaria"
                required
                value={data.timezone}
                onChange={(e) => update("timezone", e.target.value)}
                hint="Por ejemplo: America/Tegucigalpa"
              />
              <Select
                title="Tamaño del recibo"
                options={[
                  { value: "letter", label: "Carta" },
                  { value: "half_letter", label: "Media carta" },
                ]}
                value={data.paper}
                onChange={(e) => update("paper", e.target.value)}
              />
              <Input
                title="Destino externo de respaldos (opcional)"
                value={data.backup_destination}
                onChange={(e) => update("backup_destination", e.target.value)}
                placeholder="D:\RespaldosGrupoAbogados"
                hint="Ruta en el equipo principal. Vacío usa la carpeta de datos local."
              />
            </Form>
          )}
        </section>
        <section className="panel padded">
          <ShieldCheck className="muted" size={26} />
          <h3>Respaldo y recuperación</h3>
          <p>
            El sistema crea una copia al comenzar la actividad de cada día y
            conserva 30 copias diarias.
          </p>
          <p>
            Las copias incluyen base de datos, configuración, logos y recibos.
            Guarda una copia en otro disco para protegerte ante pérdida del
            equipo.
          </p>
          <div className="stack-actions">
            <button
              className="primary"
              onClick={async () => {
                try {
                  const result = await api("/backups", { method: "POST" });
                  notify("Respaldo creado: " + result.name);
                  refresh();
                } catch (err) {
                  notify(err.message, true);
                }
              }}
            >
              <Archive size={16} /> Crear respaldo ahora
            </button>
            <button
              className="secondary"
              onClick={async () => {
                try {
                  await api("/auth/close-other-sessions", { method: "POST" });
                  notify("Las demás sesiones fueron cerradas");
                } catch (err) {
                  notify(err.message, true);
                }
              }}
            >
              Cerrar otras sesiones
            </button>
            <button
              className="danger"
              onClick={() => {
                setRestore(true);
                setFile(null);
                setConfirmation("");
              }}
            >
              <RotateCcw size={16} /> Restaurar respaldo
            </button>
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-title">
          <h3>Copias disponibles</h3>
        </div>
        {backups.error && <p className="error">{backups.error}</p>}
        <Table
          rows={backups.items.map((r, i) => ({ ...r, id: i }))}
          busy={backups.busy}
          columns={[
            { key: "name", title: "Archivo" },
            {
              key: "size",
              title: "Tamaño",
              render: (r) => (r.size / 1024 / 1024).toFixed(2) + " MB",
            },
            {
              key: "action",
              title: "",
              render: (r) => (
                <a
                  className="text-button"
                  href={"/api/backups/" + encodeURIComponent(r.name)}
                >
                  <Download size={15} /> Descargar
                </a>
              ),
            },
          ]}
        />
      </section>
      {restore && (
        <Modal title="Restaurar respaldo" onClose={() => setRestore(false)}>
          <Form
            onCancel={() => setRestore(false)}
            submit="Restaurar y cerrar sesión"
            confirm
            confirmationText="Comprendo que se reemplazarán los datos actuales por el respaldo seleccionado."
            onSubmit={async () => {
              if (!file || confirmation !== "RESTAURAR")
                throw new Error("Selecciona el respaldo y escribe RESTAURAR");
              const form = new FormData();
              form.append("file", file);
              await api("/backups/restore", {
                method: "POST",
                body: form,
                headers: { "X-Confirm-Restore": "RESTAURAR" },
              });
              notify("Respaldo restaurado. Inicia sesión nuevamente.");
              onRestored();
            }}
          >
            <p className="info-box warning">
              Cierra las demás sesiones. Se creará una copia previa, se validará
              el respaldo y se cerrará tu sesión al terminar.
            </p>
            <Input
              title="Archivo de respaldo"
              type="file"
              accept=".zip"
              required
              onChange={(e) => setFile(e.target.files[0])}
            />
            <Input
              title="Escribe RESTAURAR para confirmar"
              required
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </Form>
        </Modal>
      )}
    </>
  );
}
