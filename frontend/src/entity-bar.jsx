import { useEffect, useRef, useState } from "react";
import {
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  Layers3,
} from "lucide-react";

export function EntityBar({ entities, value, allowAll, onChange }) {
  const rail = useRef(null),
    buttons = useRef([]);
  const [edges, setEdges] = useState({
    overflow: false,
    left: false,
    right: false,
  });
  const choices = [
    ...(allowAll
      ? [{ id: "", name: "Todas las lotificadoras", all: true }]
      : []),
    ...entities,
  ];
  useEffect(() => {
    const element = rail.current;
    if (!element) return;
    const measure = () =>
      setEdges({
        overflow: element.scrollWidth > element.clientWidth + 2,
        left: element.scrollLeft > 2,
        right:
          element.scrollLeft + element.clientWidth < element.scrollWidth - 2,
      });
    const resize = new ResizeObserver(measure);
    resize.observe(element);
    element.addEventListener("scroll", measure, { passive: true });
    measure();
    return () => {
      resize.disconnect();
      element.removeEventListener("scroll", measure);
    };
  }, [entities, allowAll]);
  useEffect(() => {
    buttons.current
      .find((button) => button?.getAttribute("aria-pressed") === "true")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [value, allowAll]);
  function choose(index) {
    const choice = choices[index];
    if (!choice) return;
    buttons.current[index]?.focus({ preventScroll: true });
    onChange(String(choice.id));
  }
  return (
    <div className="entity-switcher">
      <nav
        className="entity-rail"
        aria-label="Lotificadoras de trabajo"
        ref={rail}
      >
        {choices.map((choice, index) => {
          const active = String(value) === String(choice.id);
          const Icon = choice.all ? Layers3 : Building2;
          return (
            <button
              key={choice.id || "all"}
              type="button"
              ref={(element) => {
                buttons.current[index] = element;
              }}
              className={"entity-tab" + (active ? " selected" : "")}
              aria-pressed={active}
              title={
                choice.name +
                (choice.status === "archived" ? " · archivada" : "")
              }
              onClick={() => choose(index)}
              onKeyDown={(event) => {
                const next =
                  event.key === "ArrowRight"
                    ? (index + 1) % choices.length
                    : event.key === "ArrowLeft"
                      ? (index - 1 + choices.length) % choices.length
                      : event.key === "Home"
                        ? 0
                        : event.key === "End"
                          ? choices.length - 1
                          : null;
                if (next !== null) {
                  event.preventDefault();
                  choose(next);
                }
              }}
            >
              <Icon size={16} aria-hidden="true" />
              <span className="entity-tab-name">{choice.name}</span>
              {choice.status === "archived" && <small>Archivada</small>}
              {active && (
                <Check
                  className="entity-tab-check"
                  size={15}
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
        {!entities.length && (
          <span className="entity-empty">Sin lotificadoras asignadas</span>
        )}
      </nav>
      {edges.overflow && (
        <div className="entity-rail-controls">
          <button
            type="button"
            className="icon"
            aria-label="Ver lotificadoras anteriores"
            disabled={!edges.left}
            onClick={() =>
              rail.current.scrollBy({ left: -rail.current.clientWidth * 0.7 })
            }
          >
            <ChevronLeft size={18} />
          </button>
          <button
            type="button"
            className="icon"
            aria-label="Ver lotificadoras siguientes"
            disabled={!edges.right}
            onClick={() =>
              rail.current.scrollBy({ left: rail.current.clientWidth * 0.7 })
            }
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </div>
  );
}
