"use client";

import { useState } from "react";
import { call, HttpError } from "@/lib/client";
import { useBag } from "./BagProvider";

/** Back-in-stock signup shown in place of Add to Bag when the chosen size is sold out. */
export function NotifyMe({ sku, label }: { sku: string; label: string }) {
  const { customer } = useBag();
  const [email, setEmail] = useState(customer?.email ?? "");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (done) {
    return <p className="mt-4 border border-teal bg-teal/5 p-3 text-sm" role="status" data-testid="notify-done">We&apos;ll email {email} when {label} is back.</p>;
  }
  return (
    <form
      className="mt-4 border p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await call("/stock-notifications", { method: "POST", body: { sku, email } });
          setDone(true);
        } catch (err) {
          setError(err instanceof HttpError ? err.message : "Couldn't sign you up.");
        }
      }}
      data-testid="notify-form"
    >
      <p className="text-sm font-semibold">{label} is sold out</p>
      <p className="text-xs text-neutral-600">Get one email when it&apos;s back in stock.</p>
      <div className="mt-2 flex gap-2">
        <label htmlFor="notify-email" className="sr-only">Email</label>
        <input id="notify-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="input flex-1" data-testid="notify-email" />
        <button type="submit" className="btn" data-testid="notify-submit">Notify me</button>
      </div>
      {error && <p className="mt-2 text-sm text-sale" role="alert">{error}</p>}
    </form>
  );
}
