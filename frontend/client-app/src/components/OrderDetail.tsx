"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { call, HttpError } from "@/lib/client";
import { money } from "@/lib/format";
import type { Order } from "@/lib/types";
import { OrderTimeline } from "./OrderTimeline";
import { ReturnForm } from "./ReturnForm";

export function OrderDetail({ number, email, placed }: { number: string; email?: string; placed?: boolean }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);

  useEffect(() => {
    const qs = email ? `?email=${encodeURIComponent(email)}` : "";
    call<Order>(`/orders/${encodeURIComponent(number)}${qs}`).then(setOrder).catch((e) => setError(e instanceof HttpError ? e.message : "Could not load this order."));
  }, [number, email]);

  if (error) return <div className="mx-auto max-w-3xl px-4 py-16 text-center"><p className="text-lg font-semibold">{error}</p><Link href="/order-lookup" className="btn mt-6">Look up an order</Link></div>;
  if (!order) return <div className="mx-auto max-w-3xl px-4 py-16">Loading order...</div>;
  const returnOpen = new Date(order.returnBy).getTime() > Date.now();
  const returnedQty = order.returns.flatMap((r) => r.lines).reduce((n, l) => n + l.quantity, 0);
  const canReturn = returnOpen && returnedQty < order.lines.reduce((n, l) => n + l.quantity, 0);
  const invoice = `/api/orders/${order.orderNumber}/invoice?email=${encodeURIComponent(order.email)}`;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {placed && <p className="text-sm font-semibold uppercase tracking-wide text-teal">Thank you for your order</p>}
      <h1 className="mt-1 font-display text-3xl font-bold">Order <span data-testid="order-number">{order.orderNumber}</span></h1>
      <p className="mt-2 text-sm text-neutral-600">
        Placed {new Date(order.createdAt).toLocaleString()} · Status <span className="font-semibold" data-testid="order-status">{order.status}</span> · A confirmation was sent to {order.email}.
      </p>
      {order.tracking && <OrderTimeline tracking={order.tracking} />}
      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <section className="bg-sand p-5 text-sm" data-testid="fulfillment-details">
          {order.fulfillment === "PICKUP" && order.pickup ? (
            <>
              <h2 className="font-semibold">Pick up in store</h2>
              <p className="mt-2">{order.pickup.storeName}<br />{order.pickup.address}, {order.pickup.city}, {order.pickup.state} {order.pickup.zip}</p>
              <p className="mt-2">Ready in about {order.pickup.readyInHours} hr. Bring your order number and photo ID.</p>
            </>
          ) : (
            <>
              <h2 className="font-semibold">Shipping {order.shippingMethod === "EXPRESS" ? "(Express, 2 business days)" : "(Standard, 5-7 business days)"}</h2>
              {order.shipTo && <p className="mt-2">{order.shipTo.name}<br />{order.shipTo.line1}{order.shipTo.line2 ? `, ${order.shipTo.line2}` : ""}<br />{order.shipTo.city}, {order.shipTo.state} {order.shipTo.zip}</p>}
            </>
          )}
          <p className="mt-3">Paid with {order.cardBrand} ending {order.cardLast4}</p>
          {order.pointsEarned > 0 && <p className="mt-2 font-semibold text-teal">You earned {order.pointsEarned} rewards points.</p>}
          <a href={invoice} target="_blank" rel="noreferrer" className="mt-4 inline-block underline" data-testid="invoice-link">View invoice {order.invoiceNumber}</a>
        </section>
        <section>
          <ul className="divide-y border-y text-sm">
            {order.lines.map((l) => (
              <li key={l.lineNo} className="flex gap-3 py-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {l.image && <img src={l.image.replace(".webp", "-sm.webp")} alt="" className="h-20 w-16 object-cover" />}
                <div className="flex-1"><p className="font-medium">{l.name}</p><p className="text-neutral-600">{l.color} · {l.size} × {l.quantity}</p></div>
                <p>{money(l.lineTotalCents)}</p>
              </li>
            ))}
          </ul>
          <dl className="mt-4 space-y-1.5 text-sm">
            <div className="flex justify-between"><dt>Subtotal</dt><dd>{money(order.subtotalCents)}</dd></div>
            {order.discountCents > 0 && <div className="flex justify-between text-sale"><dt>Promo {order.promoCode}</dt><dd>−{money(order.discountCents)}</dd></div>}
            <div className="flex justify-between"><dt>{order.fulfillment === "PICKUP" ? "Pickup" : "Shipping"}</dt><dd>{order.shippingCents === 0 ? "Free" : money(order.shippingCents)}</dd></div>
            {order.fees.map((f) => <div key={f.code} className="flex justify-between"><dt>{f.label}</dt><dd>{money(f.amountCents)}</dd></div>)}
            <div className="flex justify-between"><dt>Tax</dt><dd>{money(order.taxCents)}</dd></div>
            <div className="flex justify-between border-t pt-2 text-base font-semibold"><dt>Total</dt><dd data-testid="confirmation-total">{money(order.totalCents)}</dd></div>
          </dl>
        </section>
      </div>
      <section className="mt-10" aria-labelledby="returns-heading" data-testid="returns">
        <h2 id="returns-heading" className="text-lg font-semibold">Returns</h2>
        {order.returns.map((r) => (
          <div key={r.returnNumber} className="mt-3 border p-4 text-sm" data-testid="return-summary">
            <p className="font-semibold">Return <span data-testid="return-number">{r.returnNumber}</span> · {r.status === "REQUESTED" ? "Requested" : r.status}</p>
            <p className="mt-1 text-neutral-600">{r.lines.reduce((n, l) => n + l.quantity, 0)} item(s) · {r.method === "MAIL" ? "Mail it back with the prepaid label we emailed." : "Bring it to any OtterShops store with this return number."}</p>
            <p className="mt-1">Refund of <span className="font-semibold" data-testid="return-refund">{money(r.refundCents)}</span> to {order.cardBrand} ending {order.cardLast4} once we receive it.</p>
          </div>
        ))}
        {returning ? (
          <ReturnForm order={order} onCancel={() => setReturning(false)} onCreated={(r) => { setOrder({ ...order, returns: [...order.returns, r] }); setReturning(false); }} />
        ) : canReturn ? (
          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
            <button type="button" onClick={() => setReturning(true)} className="btn-outline" data-testid="start-return">Start a return</button>
            <span className="text-neutral-600">Free returns until {new Date(order.returnBy).toLocaleDateString("en-US", { month: "long", day: "numeric" })}.</span>
          </div>
        ) : (
          <p className="mt-2 text-sm text-neutral-600">{returnOpen ? "Everything on this order has a return in progress." : "The 45-day return window for this order has closed."}</p>
        )}
      </section>
      <Link href="/" className="btn-outline mt-10">Continue shopping</Link>
    </div>
  );
}
