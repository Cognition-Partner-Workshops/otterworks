"use client";

import { useState } from "react";
import { call } from "@/lib/client";
import type { Store } from "@/lib/types";

export function StoreSearch({ selected, onSelect, actionLabel = "Pick up here" }: { selected?: string | null; onSelect: (s: Store) => void; actionLabel?: string }) {
  const [q, setQ] = useState("");
  const [stores, setStores] = useState<Store[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function search() {
    setBusy(true);
    try {
      setStores((await call<{ stores: Store[] }>(`/stores?q=${encodeURIComponent(q.trim())}`)).stores);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {/* Not a <form>: this renders inside the checkout form, and nested forms submit the outer one. */}
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void search();
            }
          }}
          placeholder="ZIP code or city" aria-label="ZIP code or city" className="input" data-testid="store-query" />
        <button type="button" onClick={() => void search()} disabled={busy} className="btn-outline px-4 py-2 text-sm" data-testid="store-search">Search</button>
      </div>
      {stores && stores.length === 0 && <p className="mt-3 text-sm text-neutral-600">No stores found. Try another ZIP or city.</p>}
      {stores && stores.length > 0 && (
        <ul className="mt-3 divide-y border" data-testid="store-results">
          {stores.map((s) => (
            <li key={s.id} className={`flex items-start justify-between gap-4 p-3 text-sm ${selected === s.id ? "bg-teal-light" : ""}`}>
              <div>
                <p className="font-semibold">{s.name}</p>
                <p className="text-neutral-600">{s.address}, {s.city}, {s.state} {s.zip}</p>
                <p className="text-xs text-neutral-500">{s.hours} · {s.phone}</p>
                <p className={`mt-1 text-xs font-semibold ${s.pickupEnabled ? "text-teal" : "text-neutral-500"}`}>
                  {s.pickupEnabled ? `Free pickup, ready in ${s.pickupReadyHours} hr` : "Pickup not available at this store"}
                </p>
              </div>
              <button
                type="button"
                disabled={!s.pickupEnabled}
                onClick={() => onSelect(s)}
                data-testid={`select-store-${s.id}`}
                className="shrink-0 border border-ink px-3 py-1.5 text-xs font-semibold hover:bg-ink hover:text-white disabled:cursor-not-allowed disabled:border-neutral-300 disabled:text-neutral-400 disabled:hover:bg-transparent"
              >
                {selected === s.id ? "Selected" : actionLabel}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
