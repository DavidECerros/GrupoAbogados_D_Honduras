import { Plus, Trash2 } from "lucide-react";
import { Field, Input, Picker } from "./components";

export const emptyBoundaries = () =>
  ["Norte", "Sur", "Este", "Oeste"].map((side) => ({
    side,
    bearing: "",
    distance: "",
    neighbor: "",
  }));

export function LotDeedFields({ data, update, entity }) {
  function changeSide(index, key, value) {
    update(
      "boundaries",
      data.boundaries.map((side, i) =>
        i === index ? { ...side, [key]: value } : side,
      ),
    );
  }
  return (
    <>
      <Input
        title="Código del lote"
        required
        maxLength={80}
        value={data.code}
        onChange={(e) => update("code", e.target.value)}
      />
      <fieldset className="lot-deed-section">
        <legend>Datos del cliente según la escritura</legend>
        <p className="muted">
          Selecciona un cliente registrado o escribe sus datos. Puedes conservar
          aquí la redacción de la escritura.
        </p>
        <Picker
          title="Cliente registrado (opcional)"
          entity={entity}
          collection="clients"
          value={data.registered_client_id}
          required={false}
          selectedItem={
            data.registered_client_id
              ? {
                  id: Number(data.registered_client_id),
                  name: data.deed_client_name,
                  document: data.deed_client_document,
                }
              : null
          }
          onChange={(id, client) => {
            update("registered_client_id", id || null);
            if (client) {
              update("deed_client_name", client.name);
              update("deed_client_document", client.document);
              update("deed_client_phone", client.phone);
              update("deed_client_email", client.email);
            }
          }}
        />
        <div className="form-grid">
          <Input
            title="Nombre completo según la escritura"
            required
            maxLength={150}
            value={data.deed_client_name}
            onChange={(e) => update("deed_client_name", e.target.value)}
          />
          <Input
            title="Documento del cliente"
            maxLength={80}
            value={data.deed_client_document}
            onChange={(e) => update("deed_client_document", e.target.value)}
          />
          <Input
            title="Teléfono del cliente"
            maxLength={50}
            value={data.deed_client_phone}
            onChange={(e) => update("deed_client_phone", e.target.value)}
          />
          <Input
            title="Correo del cliente (opcional)"
            type="email"
            maxLength={150}
            value={data.deed_client_email}
            onChange={(e) => update("deed_client_email", e.target.value)}
          />
        </div>
      </fieldset>
      <Field title="Dirección del terreno tal como aparece en la escritura">
        <textarea
          required
          rows={3}
          maxLength={4000}
          value={data.deed_address}
          onChange={(e) => update("deed_address", e.target.value)}
        />
      </Field>
      <fieldset className="lot-deed-section">
        <legend>Medidas y colindancias</legend>
        <p className="muted">
          Transcribe cada lado de la escritura. Las distancias se registran en
          metros; el rumbo es opcional.
        </p>
        {data.boundaries.map((side, index) => (
          <div className="lot-boundary" key={index}>
            <div className="section-head">
              <strong>Lado {index + 1}</strong>
              <button
                type="button"
                className="icon"
                aria-label={`Quitar lado ${index + 1}`}
                disabled={data.boundaries.length <= 1}
                onClick={() =>
                  update(
                    "boundaries",
                    data.boundaries.filter((_, i) => i !== index),
                  )
                }
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="form-grid">
              <Input
                title={`Lado o dirección ${index + 1}`}
                required
                maxLength={80}
                value={side.side}
                onChange={(e) => changeSide(index, "side", e.target.value)}
              />
              <Input
                title={`Medida en metros ${index + 1}`}
                required
                type="number"
                min="0.0001"
                step="0.0001"
                value={side.distance}
                onChange={(e) => changeSide(index, "distance", e.target.value)}
              />
              <Input
                title={`Rumbo ${index + 1} (opcional)`}
                maxLength={100}
                placeholder={"Ej. N 75°07′08″ O"}
                value={side.bearing}
                onChange={(e) => changeSide(index, "bearing", e.target.value)}
              />
              <Input
                title={`Colindancia ${index + 1}`}
                required
                maxLength={500}
                value={side.neighbor}
                onChange={(e) => changeSide(index, "neighbor", e.target.value)}
              />
            </div>
          </div>
        ))}
        <button
          type="button"
          className="secondary"
          disabled={data.boundaries.length >= 100}
          onClick={() =>
            update("boundaries", [
              ...data.boundaries,
              { side: "", bearing: "", distance: "", neighbor: "" },
            ])
          }
        >
          <Plus size={16} />
          Agregar lado
        </button>
      </fieldset>
    </>
  );
}
