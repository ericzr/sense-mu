"use client";

import { Check, ChevronDown, SlidersHorizontal } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

export type CatalogFilterGroup = {
  id: string;
  label: string;
  value: string;
  allValue: string;
  options: string[];
  onChange: (value: string) => void;
};

type CatalogFilterMenuProps = {
  title: string;
  defaultLabel: string;
  groups: CatalogFilterGroup[];
};

export function CatalogFilterMenu({ title, defaultLabel, groups }: CatalogFilterMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const selectedLabels = useMemo(
    () => groups.flatMap((group) => group.value === group.allValue ? [] : [group.value]),
    [groups],
  );
  const triggerLabel = selectedLabels.length === 0
    ? defaultLabel
    : selectedLabels.length === 1
      ? selectedLabels[0]
      : `已选 ${selectedLabels.length} 项`;

  useEffect(() => {
    function closeOnOutsideClick(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function reset() {
    groups.forEach((group) => group.onChange(group.allValue));
  }

  return (
    <div className={`catalog-filter-menu${open ? " is-open" : ""}`} ref={rootRef}>
      <button
        className="catalog-filter-trigger"
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <SlidersHorizontal size={14} aria-hidden="true" />
        <span>{triggerLabel}</span>
        {selectedLabels.length ? <small>{selectedLabels.length}</small> : null}
        <ChevronDown size={14} aria-hidden="true" />
      </button>

      {open ? (
        <section className="catalog-filter-panel" id={panelId} aria-label={title}>
          <header>
            <strong>{title}</strong>
            <button type="button" disabled={!selectedLabels.length} onClick={reset}>重置</button>
          </header>
          <div className="catalog-filter-groups">
            {groups.map((group) => (
              <div className="catalog-filter-group" key={group.id}>
                <span>{group.label}</span>
                <div>
                  {group.options.map((option) => {
                    const selected = group.value === option;
                    return (
                      <button
                        className={selected ? "is-selected" : ""}
                        type="button"
                        aria-pressed={selected}
                        key={option}
                        onClick={() => group.onChange(option)}
                      >
                        {selected ? <Check size={11} aria-hidden="true" /> : null}
                        {option}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <footer><button type="button" onClick={() => setOpen(false)}>完成</button></footer>
        </section>
      ) : null}
    </div>
  );
}
