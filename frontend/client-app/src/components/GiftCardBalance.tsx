"use client";

import { useState } from "react";
import { call, HttpError } from "@/lib/client";
import { money } from "@/lib/format";
import type { GiftCardBalance as Balance } from "@/lib/types";

export function GiftCardBalance() {
  const [number, setNumber] = useState("");
  const [pin, setPin] = useState("");
  const [result, setResult] = useState<Balance | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="mt-8 max-w-md space-y-3 border p-5"
      aria-labelledby="gc-heading"
      data-testid="gift-card-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null); setResult(null);
        try { setResult(await call<Balance>("/gift-cards/balance", { method: "POST", body: { number, pin } })); }
        catch (err) { setError(err instanceof HttpError ? err.message : "Couldn't check that card."); }
      }}
    >
      <h2 id="gc-heading" className="text-lg font-semibold">Check your balance</h2>
      <label className="block text-sm">Card number
        <input value={number} onChange={(e) => setNumber(e.target.value)} inputMode="numeric" autoComplete="off" required placeholder="16 digits" className="input mt-1" data-testid="gc-number" />
      </label>
      <label className="block text-sm">PIN
        <input value={pin} onChange={(e) => setPin(e.target.value)} inputMode="numeric" autoComplete="off" required maxLength={4} type="password" placeholder="4 digits" className="input mt-1" data-testid="gc-pin" />
      </label>
      <button type="submit" className="btn w-full" data-testid="gc-submit">Check balance</button>
      <div aria-live="polite">
        {result && (
          <p className="bg-teal-light p-3 text-sm" data-testid="gc-result">
            Card ending {result.last4} has <span className="font-semibold" data-testid="gc-balance">{money(result.balanceCents)}</span> left{result.expiresOn ? `, use by ${new Date(result.expiresOn + "T12:00:00").toLocaleDateString()}` : ""}.
          </p>
        )}
        {error && <p className="text-sm text-sale" role="alert" data-testid="gc-error">{error}</p>}
      </div>
      <p className="text-xs text-neutral-500">Demo cards: 6006 4912 3456 7890 with PIN 1234, or 6006 4955 5544 4433 with PIN 4321.</p>
    </form>
  );
}
