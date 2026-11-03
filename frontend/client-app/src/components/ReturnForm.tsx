"use client";

import { useEffect, useState } from "react";
import { call, HttpError } from "@/lib/client";
import { money } from "@/lib/format";
import type { Order, ReturnView } from "@/lib/types";

export function ReturnForm({ order, onCreated, onCancel }: { order: Order; onCreated: (r: ReturnView) => void; onCancel: () => void }) {
  const [reasons, setReasons] = useState<string[]>([]);
  const [picked, setPicked] = useState<Record<number, { qty: number; reason: string }>>({});
  const [method, setMethod] = useState<"MAIL" | "STORE">("MAIL");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { call<string[]>("/returns/reasons").then(setReasons).catch(() => setReasons([])); }, []);

  const returned = (lineNo: number) => order.returns.flatMap((r) => r.lines).filter((l) => l.lineNo === lineNo).reduce((n, l) => n + l.quantity, 0);
  const lines = order.lines.map((l) => ({ ...l, left: l.quantity - returned(l.lineNo) })).filter((l) => l.left > 0);

  return (
    <form
      className="mt-6 space-y-4 border p-5"
      aria-label="Start a return"
      data-testid="return-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const chosen = Object.entries(picked).map(([lineNo, v]) => ({ lineNo: Number(lineNo), quantity: v.qty, reason: v.reason }));
        if (chosen.length === 0) { setError("Choose at least one item to return."); return; }
        if (chosen.some((c) => !c.reason)) { setError("Pick a reason for each item."); return; }
        setBusy(true); setError(null);
        try {
          onCreated(await call<ReturnView>(`/orders/${order.orderNumber}/returns`, { method: "POST", body: { email: order.email, method, lines: chosen } }));
        } catch (err) {
          setError(err instanceof HttpError ? err.message : "Couldn't start the return.");
        } finally { setBusy(false); }
      }}
    >
      <h2 className="text-lg font-semibold">Start a return</h2>
      <ul className="divide-y">
        {lines.map((l) => {
          const p = picked[l.lineNo];
          return (
            <li key={l.lineNo} className="py-3 text-sm">
              <label className="flex items-center gap-3">
                <input type="checkbox" checked={!!p} data-testid={`return-line-${l.lineNo}`}
                  onChange={(e) => setPicked((s) => { const n = { ...s }; if (e.target.checked) n[l.lineNo] = { qty: l.left, reason: "" }; else delete n[l.lineNo]; return n; })} />
                <span className="flex-1">{l.name} · {l.color} · {l.size}</span>
                <span>{money(l.lineTotalCents)}</span>
              </label>
              {p && (
                <div className="ml-7 mt-2 flex flex-wrap gap-3">
                  <label className="flex items-center gap-1">Qty
                    <select value={p.qty} onChange={(e) => setPicked((s) => ({ ...s, [l.lineNo]: { ...p, qty: Number(e.target.value) } }))} className="border px-2 py-1">
                      {Array.from({ length: l.left }, (_, i) => i + 1).map((n) => <option key={n}>{n}</option>)}
                    </select>
                  </label>
                  <label className="flex items-center gap-1">Reason
                    <select value={p.reason} onChange={(e) => setPicked((s) => ({ ...s, [l.lineNo]: { ...p, reason: e.target.value } }))} className="border px-2 py-1" data-testid={`return-reason-${l.lineNo}`}>
                      <option value="">Choose</option>{reasons.map((r) => <option key={r}>{r}</option>)}
                    </select>
                  </label>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <fieldset>
        <legend className="text-sm font-semibold">How will you send it back?</legend>
        <div className="mt-2 flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="radio" name="method" checked={method === "MAIL"} onChange={() => setMethod("MAIL")} /> Free mail return (prepaid label)</label>
          <label className="flex items-center gap-2"><input type="radio" name="method" checked={method === "STORE"} onChange={() => setMethod("STORE")} data-testid="return-store" /> Drop off at any store</label>
        </div>
      </fieldset>
      {error && <p className="text-sm text-sale" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn" data-testid="return-submit">Submit return</button>
        <button type="button" onClick={onCancel} className="btn-outline">Cancel</button>
      </div>
    </form>
  );
}
