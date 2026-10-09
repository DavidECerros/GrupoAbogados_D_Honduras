import { useEffect, useState } from "react";
import { Download, Upload, Database, FolderInput } from "lucide-react";
import { api } from "./api";
import { Field, Form, Input, Modal, Select, Table } from "./components";

export function CatalogImport({ kind, entity, onClose, onSaved }) {
  const [file, setFile] = useState(null),
    [mode, setMode] = useState("create"),
    [reason, setReason] = useState(""),
    [preview, setPreview] = useState(null),
    [confirmation, setConfirmation] = useState("");
  const title = kind === "clients" ? "clientes" : "lotes";
  return (
    <Modal title={"Importar " + title} onClose={onClose} wide>
      <p>
        La importación se aplica a la lotificadora seleccionada. Se valida todo
        el archivo antes de guardar.
      </p>
      <a className="text-button" href={`/api/catalogs/${kind}/template.xlsx`}>
        <Download size={16} /> Descargar plantilla Excel
      </a>
      {!preview ? (
        <Form
          submit="Revisar archivo"
          onCancel={onClose}
          onSubmit={async () => {
            if (!file) throw new Error("Selecciona un archivo");
            const body = new FormData();
            body.append("file", file);
            body.append("mode", mode);
            body.append("reason", reason);
            setPreview(
              await api(`/entities/${entity}/catalogs/${kind}/import/preview`, {
                method: "POST",
                body,
              }),
            );
          }}
        >
          <Input
            title="Archivo Excel o CSV UTF-8"
            type="file"
            accept=".xlsx,.csv"
            required
            onChange={(e) => setFile(e.target.files[0])}
          />
          <Select
            title="Cómo importar"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            options={[
              { value: "create", label: "Solo crear nuevos" },
              { value: "upsert", label: "Crear y actualizar existentes" },
            ]}
          />
          <Input
            title="Motivo de la importación"
            required
            minLength={3}
            maxLength={2000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Form>
      ) : (
        <>
          <p className="info-box">
            {preview.total} filas · {preview.create} nuevas · {preview.update}{" "}
            actualizaciones · {preview.error_count} errores.
          </p>
          {preview.error_count > 0 ? (
            <>
              <p className="error">
                No se guardará ninguna fila mientras haya errores. Corrige el
                archivo y vuelve a revisarlo.
              </p>
              <Table
                rows={preview.errors.map((r) => ({ ...r, id: r.line }))}
                columns={[
                  { key: "line", title: "Fila" },
                  { key: "message", title: "Error" },
                ]}
              />
            </>
          ) : (
            <>
              <p>
                Vista previa de las primeras 100 filas. Se creará un respaldo
                antes de importar todas las filas.
              </p>
              <Table
                rows={preview.rows.map((r) => ({
                  ...r,
                  id: r.line,
                  name: r.data.name || r.data.code,
                  operation: r.operation === "create" ? "Crear" : "Actualizar",
                }))}
                columns={[
                  { key: "line", title: "Fila" },
                  { key: "name", title: "Registro" },
                  { key: "operation", title: "Acción" },
                ]}
              />
              <Form
                submit="Confirmar importación"
                confirm
                onCancel={() => setPreview(null)}
                onSubmit={async () => {
                  const result = await api("/catalogs/import/execute", {
                    method: "POST",
                    body: { token: preview.token, confirmation },
                  });
                  onSaved(result);
                }}
              >
                <Input
                  title="Escribe IMPORTAR"
                  required
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </Form>
            </>
          )}
          <button
            className="text-button"
            onClick={() => {
              setPreview(null);
              setConfirmation("");
            }}
          >
            Elegir o corregir archivo
          </button>
        </>
      )}
    </Modal>
  );
}

export function DatabasePanel({ version, refresh, notify, onRestore }) {
  const [info, setInfo] = useState(null),
    [error, setError] = useState(""),
    [sql, setSql] = useState(
      "SELECT id, name, document, status FROM clients LIMIT 100;",
    ),
    [reason, setReason] = useState(""),
    [preview, setPreview] = useState(null),
    [confirmation, setConfirmation] = useState(""),
    [moving, setMoving] = useState(false),
    [target, setTarget] = useState(""),
    [moveReason, setMoveReason] = useState(""),
    [moved, setMoved] = useState(null);
  useEffect(() => {
    api("/admin/database")
      .then(setInfo)
      .catch((e) => setError(e.message));
  }, [version]);
  if (moved)
    return (
      <section className="panel padded">
        <h3>Datos trasladados</h3>
        <p>
          La nueva carpeta es <strong>{moved.path}</strong>.
        </p>
        <p>
          El sistema está pausado. Cierra la ventana del servidor con Ctrl+C y
          vuelve a abrir Iniciar.cmd. Entrarás con el mismo usuario y los mismos
          datos.
        </p>
        <p>La carpeta original se conserva en {moved.original_retained}.</p>
      </section>
    );
  return (
    <>
      {error && <p className="error">{error}</p>}
      <section className="panel padded">
        <h3>
          <Database size={18} /> Base de datos principal
        </h3>
        {info && (
          <>
            <p>
              Archivo: <strong>{info.file}</strong>
            </p>
            <p>Carpeta completa: {info.path}</p>
          </>
        )}
        <div className="row-actions">
          <a className="secondary" href="/api/admin/database/export.sqlite3">
            <Download size={16} /> Descargar SQLite
          </a>
          <a className="secondary" href="/api/export.xlsx">
            <Download size={16} /> Exportar datos a Excel
          </a>
          <button
            className="secondary"
            onClick={async () => {
              try {
                const result = await api("/backups", { method: "POST" });
                notify("Respaldo completo creado: " + result.name);
                refresh();
              } catch (e) {
                notify(e.message, true);
              }
            }}
          >
            Crear respaldo completo
          </button>
          <button className="secondary" onClick={onRestore}>
            <Upload size={16} /> Importar o restaurar respaldo
          </button>
          <button className="secondary" onClick={() => setMoving(true)}>
            <FolderInput size={16} /> Mover carpeta de datos
          </button>
        </div>
        <p>
          El archivo SQLite contiene las tablas. El respaldo ZIP incluye además
          los recibos y logos. La restauración completa se realiza en
          Configuración.
        </p>
        <p>
          Clientes y lotes se pueden importar desde sus secciones con las
          plantillas Excel.
        </p>
      </section>
      <section className="panel padded">
        <h3>Editor SQL del superusuario</h3>
        <Input
          title="Cargar una sentencia desde archivo SQL (opcional)"
          type="file"
          accept=".sql,.txt"
          onChange={async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (file.size > 20000) {
              notify("Archivo SQL máximo 20 KB", true);
              return;
            }
            setSql(await file.text());
            setPreview(null);
          }}
        />
        <p className="info-box warning">
          La edición directa puede cambiar contratos, saldos y recibos de forma
          inconsistente. Revisa el resultado antes de confirmar. El sistema
          conserva las relaciones obligatorias y la auditoría. No permite
          cambiar el esquema, abrir otros archivos ni desactivar sus
          restricciones.
        </p>
        <Form
          submit="Consultar o previsualizar"
          onSubmit={async () => {
            setPreview(
              await api("/admin/database/sql/preview", {
                method: "POST",
                body: { sql, reason },
              }),
            );
            setConfirmation("");
          }}
        >
          <Field title="Sentencia SQL">
            <textarea
              className="sql-editor"
              required
              maxLength={20000}
              rows={7}
              value={sql}
              onChange={(e) => {
                setSql(e.target.value);
                setPreview(null);
              }}
            />
          </Field>
          <Input
            title="Motivo de la consulta o modificación"
            required
            minLength={3}
            maxLength={2000}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setPreview(null);
            }}
          />
        </Form>
        {preview && (
          <>
            <p className="info-box">
              {preview.writes
                ? `${preview.changes} cambios previstos. Todavía no se han guardado.`
                : "Resultado de consulta. No se modificaron datos."}{" "}
              Tablas: {preview.tables.join(", ")}.
            </p>
            {!!preview.columns.length && (
              <Table
                rows={preview.rows.map((row, index) => ({
                  id: index,
                  ...Object.fromEntries(
                    row.map((value, col) => [
                      "c" + col,
                      typeof value === "object" ? JSON.stringify(value) : value,
                    ]),
                  ),
                }))}
                columns={preview.columns.map((title, index) => ({
                  key: "c" + index,
                  title,
                }))}
              />
            )}
            {preview.truncated && (
              <p>Se muestran los primeros 200 resultados.</p>
            )}
            {preview.writes && (
              <Form
                submit="Ejecutar modificación"
                confirm
                confirmationText="Comprendo que este SQL modifica directamente la base de datos. Se creará un respaldo previo."
                onSubmit={async () => {
                  const result = await api("/admin/database/sql/execute", {
                    method: "POST",
                    body: { token: preview.token, confirmation },
                  });
                  setPreview(null);
                  refresh();
                  notify(
                    `${result.changes} cambios guardados. Respaldo: ${result.backup}`,
                  );
                }}
              >
                <Input
                  title="Escribe EJECUTAR"
                  required
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </Form>
            )}
          </>
        )}
      </section>
      {info && (
        <section className="panel padded">
          <h3>Tablas y columnas</h3>
          <p>
            Los importes monetarios internos se guardan en centavos: 100.00
            equivale a 10000. Ejecuta una sentencia por vez.
          </p>
          <Table
            rows={info.tables.map((table, index) => ({
              ...table,
              id: index,
              columns: table.columns
                .map((c) => `${c.name} (${c.type})`)
                .join(", "),
            }))}
            columns={[
              { key: "name", title: "Tabla" },
              { key: "rows", title: "Registros" },
              { key: "columns", title: "Columnas" },
            ]}
          />
        </section>
      )}
      {moving && (
        <Modal title="Mover carpeta de datos" onClose={() => setMoving(false)}>
          <Form
            submit="Preparar traslado y pausar"
            confirm
            confirmationText="Cerraré el servidor y lo iniciaré de nuevo al finalizar el traslado."
            onCancel={() => setMoving(false)}
            onSubmit={async () => {
              const result = await api("/admin/database/location", {
                method: "POST",
                body: { path: target, reason: moveReason, confirmation },
              });
              setMoving(false);
              setMoved(result);
            }}
          >
            <p>
              Usa una carpeta vacía en un disco del equipo principal. Se
              copiarán la base, los recibos, logos y respaldos. La carpeta
              original se conserva.
            </p>
            <p>
              No uses una carpeta compartida ni sincronizada para la base
              activa. Puedes descargar los ZIP de respaldo y guardarlos donde
              prefieras.
            </p>
            {info?.environment_override && (
              <p className="error">
                Esta instalación usa GESTOR_DATA_DIR; el traslado requiere
                detener el servidor y actualizar esa variable.
              </p>
            )}
            <Input
              title="Nueva carpeta de datos"
              required
              placeholder="D:\\GrupoAbogadosDatos"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
            <Input
              title="Motivo del traslado"
              required
              minLength={3}
              value={moveReason}
              onChange={(e) => setMoveReason(e.target.value)}
            />
            <Input
              title="Escribe MOVER"
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
