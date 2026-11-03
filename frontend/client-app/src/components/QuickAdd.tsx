"use client";

import { useEffect, useRef, useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { ProductDetail } from "@/lib/types";
import { useBag } from "./BagProvider";

/** Size picker over a listing card so shoppers can add to bag without leaving the grid. */
export function QuickAdd({ productId, name }: { productId: string; name: string }) {
  const { add } = useBag();
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || detail) return;
    call<ProductDetail>(`/products/${productId}`).then((d) => {
      setDetail(d);
      setColor(d.colors.find((c) => !c.soldOut)?.name ?? d.colors[0]?.name ?? null);
    }).catch(() => setError("Couldn't load sizes"));
  }, [open, detail, productId]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    panel.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const skus = detail?.skus.filter((s) => s.color === color) ?? [];

  if (!open) {
    return (
      <div className="pointer-events-none absolute inset-x-0 top-0 flex aspect-[4/5] items-end p-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="pointer-events-auto w-full bg-white/95 py-2 text-sm font-semibold opacity-0 shadow transition-opacity focus:opacity-100 group-hover:opacity-100"
          aria-label={`Quick add ${name}`}
          data-testid="quick-add"
        >
          Quick add
        </button>
      </div>
    );
  }
  return (
    <div ref={panel} tabIndex={-1} role="dialog" aria-label={`Quick add ${name}`} className="absolute inset-x-0 top-0 z-20 bg-white p-3 shadow-xl ring-1 ring-neutral-200" data-testid="quick-add-panel">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">{name}</p>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close quick add" className="text-xl leading-none">×</button>
      </div>
      {!detail && !error && <p className="mt-2 text-sm text-neutral-600">Loading sizes...</p>}
      {detail && (
        <>
          <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Color">
            {detail.colors.map((c) => (
              <button key={c.name} type="button" role="radio" aria-checked={color === c.name} aria-label={c.name} title={c.name} onClick={() => setColor(c.name)}
                className={`h-6 w-6 rounded-full border ${color === c.name ? "ring-2 ring-teal ring-offset-1" : ""}`} style={{ background: c.hex }} />
            ))}
          </div>
          <p className="mt-2 text-xs text-neutral-600">{color}</p>
          <div className="mt-2 grid grid-cols-4 gap-1">
            {skus.map((s) => (
              <button key={s.sku} type="button" disabled={s.soldOut || busy}
                onClick={async () => {
                  setBusy(true); setError(null);
                  try { await add(s.sku, 1); setOpen(false); } catch (e) { setError(e instanceof HttpError ? e.message : "Couldn't add"); } finally { setBusy(false); }
                }}
                className={`border py-1.5 text-xs ${s.soldOut ? "cursor-not-allowed text-neutral-400 line-through" : "hover:border-ink"}`}
                aria-label={`Add size ${s.size}${s.soldOut ? " (sold out)" : ""}`}
                data-testid="quick-add-size"
              >{s.size}</button>
            ))}
          </div>
        </>
      )}
      {error && <p className="mt-2 text-sm text-sale" role="alert">{error}</p>}
    </div>
  );
}
