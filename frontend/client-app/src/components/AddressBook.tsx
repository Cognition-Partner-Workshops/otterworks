"use client";

import { useCallback, useEffect, useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { SavedAddress } from "@/lib/types";

const EMPTY = { label: "", name: "", line1: "", line2: "", city: "", state: "", zip: "", phone: "", isDefault: false };

export function AddressBook() {
  const [list, setList] = useState<SavedAddress[] | null>(null);
  const [form, setForm] = useState<typeof EMPTY | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setList(await call<SavedAddress[]>("/account/addresses")), []);
  useEffect(() => { void load().catch(() => setList([])); }, [load]);

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try { await fn(); await load(); } catch (e) { setError(e instanceof HttpError ? e.message : "Something went wrong."); }
  }

  const field = (k: keyof typeof EMPTY, label: string, opts: { required?: boolean; className?: string; maxLength?: number; autoComplete?: string } = {}) => (
    <label className={`block text-sm ${opts.className ?? ""}`}>{label}
      <input value={String(form![k])} required={opts.required} maxLength={opts.maxLength} autoComplete={opts.autoComplete}
        onChange={(e) => setForm({ ...form!, [k]: e.target.value })} className="input mt-1" data-testid={`addr-${k}`} />
    </label>
  );

  return (
    <section className="mt-10" aria-labelledby="addr-heading" data-testid="address-book">
      <div className="flex items-baseline justify-between">
        <h2 id="addr-heading" className="text-xl font-semibold">Address book</h2>
        {!form && <button type="button" className="text-sm underline" onClick={() => setForm({ ...EMPTY, isDefault: (list?.length ?? 0) === 0 })} data-testid="add-address">Add an address</button>}
      </div>
      {error && <p className="mt-2 text-sm text-sale" role="alert">{error}</p>}
      {form && (
        <form className="mt-4 grid gap-3 border p-4 sm:grid-cols-6" aria-label="New address"
          onSubmit={(e) => { e.preventDefault(); void run(async () => { await call("/account/addresses", { method: "POST", body: form }); setForm(null); }); }}>
          {field("label", "Label (Home, Work)", { className: "sm:col-span-2", maxLength: 30 })}
          {field("name", "Full name", { required: true, className: "sm:col-span-4", autoComplete: "name" })}
          {field("line1", "Street address", { required: true, className: "sm:col-span-4", autoComplete: "address-line1" })}
          {field("line2", "Apt, suite", { className: "sm:col-span-2", autoComplete: "address-line2" })}
          {field("city", "City", { required: true, className: "sm:col-span-3", autoComplete: "address-level2" })}
          {field("state", "State", { required: true, className: "sm:col-span-1", maxLength: 2, autoComplete: "address-level1" })}
          {field("zip", "ZIP", { required: true, className: "sm:col-span-2", maxLength: 10, autoComplete: "postal-code" })}
          {field("phone", "Phone", { className: "sm:col-span-3", autoComplete: "tel" })}
          <label className="flex items-center gap-2 text-sm sm:col-span-3 sm:self-end">
            <input type="checkbox" checked={form.isDefault} onChange={(e) => setForm({ ...form, isDefault: e.target.checked })} /> Make this my default
          </label>
          <div className="flex gap-2 sm:col-span-6">
            <button type="submit" className="btn" data-testid="save-address">Save address</button>
            <button type="button" className="btn-outline" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </form>
      )}
      {list && list.length === 0 && !form && <p className="mt-3 text-sm text-neutral-600">No saved addresses. Save one to check out faster.</p>}
      {list && list.length > 0 && (
        <ul className="mt-4 grid gap-4 sm:grid-cols-2">
          {list.map((a) => (
            <li key={a.id} className={`border p-4 text-sm ${a.isDefault ? "border-teal" : ""}`} data-testid="address-card">
              <p className="font-semibold">{a.label || "Address"}{a.isDefault && <span className="ml-2 bg-teal px-2 py-0.5 text-xs text-white">Default</span>}</p>
              <p className="mt-1">{a.name}<br />{a.line1}{a.line2 ? `, ${a.line2}` : ""}<br />{a.city}, {a.state} {a.zip}</p>
              {a.phone && <p className="text-neutral-600">{a.phone}</p>}
              <div className="mt-3 flex gap-4">
                {!a.isDefault && <button type="button" className="underline" onClick={() => run(() => call(`/account/addresses/${a.id}/default`, { method: "POST" }))} data-testid="make-default">Make default</button>}
                <button type="button" className="underline" aria-label={`Delete ${a.label || "address"} ${a.line1}`} onClick={() => run(() => call(`/account/addresses/${a.id}`, { method: "DELETE" }))}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
