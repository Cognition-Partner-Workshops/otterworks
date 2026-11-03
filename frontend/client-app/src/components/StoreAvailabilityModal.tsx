"use client";

import { useCallback, useEffect, useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { Availability } from "@/lib/types";
import { Modal } from "./Modal";

const LEVEL = { IN_STOCK: "In stock", LIMITED: "Limited stock", UNAVAILABLE: "Not available" } as const;

export function StoreAvailabilityModal({ productId, sku, label, onClose }: { productId: string; sku: string; label: string; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [data, setData] = useState<Availability | null>(null);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (term: string) => {
    setError(null);
    try {
      setData(await call<Availability>(`/products/${productId}/availability?sku=${encodeURIComponent(sku)}&q=${encodeURIComponent(term)}`));
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Couldn't check stores.");
    }
  }, [productId, sku]);

  useEffect(() => { void search(""); }, [search]);

  return (
    <Modal title="Check store availability" onClose={onClose} testId="store-availability">
      <p className="text-sm text-neutral-600">{label}</p>
      <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); void search(q); }}>
        <label htmlFor="avail-q" className="sr-only">City, state or ZIP</label>
        <input id="avail-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="City, state or ZIP" className="input flex-1" data-testid="avail-query" />
        <button type="submit" className="btn">Search</button>
      </form>
      {error && <p className="mt-3 text-sm text-sale" role="alert">{error}</p>}
      {data && (
        <ul className="mt-4 divide-y" aria-live="polite" data-testid="avail-results">
          {data.stores.length === 0 && <li className="py-3 text-sm">No stores match that search.</li>}
          {data.stores.map((s) => (
            <li key={s.storeId} className="flex items-start justify-between gap-4 py-3 text-sm" data-testid="avail-store">
              <div>
                <p className="font-semibold">{s.storeName}</p>
                <p className="text-neutral-600">{s.address}, {s.city}, {s.state} {s.zip}</p>
                <p className="text-neutral-600">{s.hours}</p>
              </div>
              <div className="text-right">
                <p className={s.level === "IN_STOCK" ? "font-semibold text-teal" : s.level === "LIMITED" ? "font-semibold text-sale" : "text-neutral-500"} data-testid="avail-level">
                  {LEVEL[s.level]}
                </p>
                {s.canPickUp ? <p className="text-xs text-neutral-600">Pickup ready in {s.readyInHours} hrs</p> : !s.pickupEnabled ? <p className="text-xs text-neutral-500">No pickup at this store</p> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs text-neutral-500">Choose store pickup at checkout. Store stock updates through the day, so limited items can sell out.</p>
    </Modal>
  );
}
