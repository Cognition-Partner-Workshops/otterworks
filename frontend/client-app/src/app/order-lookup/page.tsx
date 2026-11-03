"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { Order } from "@/lib/types";

export default function OrderLookupPage() {
  const router = useRouter();
  const [number, setNumber] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const o = await call<Order>(`/orders/lookup?number=${encodeURIComponent(number.trim().toUpperCase())}&email=${encodeURIComponent(email.trim())}`);
      router.push(`/order/${o.orderNumber}?email=${encodeURIComponent(o.email)}`);
    } catch (err) {
      setError(err instanceof HttpError && err.status === 404 ? "We couldn't find an order with that number and email." : "Lookup failed. Try again.");
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="font-display text-3xl font-bold">Order lookup</h1>
      <p className="mt-2 text-sm text-neutral-600">Enter the order number from your confirmation (for example OS-100123) and the email you used.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block"><span className="label">Order number</span><input required className="input" value={number} onChange={(e) => setNumber(e.target.value)} data-testid="lookup-number" /></label>
        <label className="block"><span className="label">Email</span><input required type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="lookup-email" /></label>
        {error && <p className="text-sm text-sale" role="alert">{error}</p>}
        <button type="submit" className="btn w-full" data-testid="lookup-submit">Find my order</button>
      </form>
    </div>
  );
}
