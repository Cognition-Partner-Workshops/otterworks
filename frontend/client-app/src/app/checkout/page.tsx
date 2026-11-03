"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useBag } from "@/components/BagProvider";
import { StoreSearch } from "@/components/StoreSearch";
import { call, HttpError } from "@/lib/client";
import { money } from "@/lib/format";
import { STATES } from "@/lib/states";
import type { Order, Quote, Store } from "@/lib/types";

type Fulfillment = "SHIP" | "PICKUP";
type Method = "STANDARD" | "EXPRESS";

export default function CheckoutPage() {
  const { bag, customer, ready, reset, refresh } = useBag();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [fulfillment, setFulfillment] = useState<Fulfillment>("SHIP");
  const [method, setMethod] = useState<Method>("STANDARD");
  const [addr, setAddr] = useState({ name: "", line1: "", line2: "", city: "", state: "CA", zip: "" });
  const [phone, setPhone] = useState("");
  const [store, setStore] = useState<Store | null>(null);
  const [card, setCard] = useState({ number: "", exp: "", cvc: "", name: "" });
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [placing, setPlacing] = useState(false);

  useEffect(() => {
    if (customer) setEmail((e) => e || customer.email);
  }, [customer]);

  const bagId = bag?.id;
  const bagVersion = bag ? `${bag.itemCount}-${bag.merchandiseCents}` : "";
  useEffect(() => {
    if (!bagId) return;
    if (fulfillment === "PICKUP" && !store) {
      setQuote(null);
      return;
    }
    const body = { bagId, fulfillment, shippingMethod: fulfillment === "SHIP" ? method : null, shipState: addr.state, storeId: store?.id };
    call<Quote>("/checkout/quote", { method: "POST", body }).then(setQuote).catch(() => setQuote(null));
  }, [bagId, bagVersion, fulfillment, method, addr.state, store]);

  if (!ready) return <div className="mx-auto max-w-5xl px-4 py-10">Loading checkout...</div>;
  if (!bag || bag.items.length === 0) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center">
        <h1 className="font-display text-3xl font-bold">Your bag is empty</h1>
        <Link href="/" className="btn mt-6">Keep shopping</Link>
      </div>
    );
  }

  async function place(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (fulfillment === "PICKUP" && !store) {
      setError("Choose a pickup store.");
      return;
    }
    const [mm, yy] = card.exp.split("/").map((s) => parseInt(s.trim(), 10));
    setPlacing(true);
    try {
      const order = await call<Order>("/checkout", {
        method: "POST",
        body: {
          bagId: bag!.id, email, fulfillment,
          shippingMethod: fulfillment === "SHIP" ? method : null,
          address: fulfillment === "SHIP" ? addr : null,
          phone: phone || null,
          storeId: fulfillment === "PICKUP" ? store?.id : null,
          card: { number: card.number.replace(/\s+/g, ""), expMonth: mm || null, expYear: yy ? (yy < 100 ? 2000 + yy : yy) : null, cvc: card.cvc, name: card.name },
        },
      });
      reset();
      await refresh();
      router.push(`/order/${order.orderNumber}?email=${encodeURIComponent(order.email)}&placed=1`);
    } catch (err) {
      if (err instanceof HttpError && err.status === 402) setError(`${err.message} No order was placed and you have not been charged.`);
      else setError(err instanceof HttpError ? err.message : "Could not place your order. Please try again.");
      setPlacing(false);
    }
  }

  const t = quote?.totals;
  const field = (k: keyof typeof addr, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className="block">
      <span className="label">{label}</span>
      <input className="input" value={addr[k]} onChange={(e) => setAddr({ ...addr, [k]: e.target.value })} name={k} data-testid={`ship-${k}`} {...props} />
    </label>
  );

  return (
    <form onSubmit={place} className="mx-auto grid max-w-6xl gap-10 px-4 py-8 md:grid-cols-[1fr_380px]">
      <div className="space-y-8">
        <h1 className="font-display text-3xl font-bold">Checkout</h1>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">1. Contact</h2>
          {customer ? (
            <p className="text-sm">Signed in as <span className="font-semibold">{customer.email}</span>. You&apos;ll earn points on this order.</p>
          ) : (
            <p className="text-sm text-neutral-600">Checking out as a guest. <Link href="/account/sign-in?next=/checkout" className="underline">Sign in</Link> to earn rewards.</p>
          )}
          <label className="block">
            <span className="label">Email</span>
            <input type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="email" />
          </label>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">2. Delivery</h2>
          <div className="grid grid-cols-2 gap-3">
            {(["SHIP", "PICKUP"] as const).map((f) => (
              <button key={f} type="button" onClick={() => setFulfillment(f)} aria-pressed={fulfillment === f} data-testid={`fulfillment-${f}`}
                className={`border p-4 text-left text-sm ${fulfillment === f ? "border-teal ring-2 ring-teal" : "border-neutral-300"}`}>
                <p className="font-semibold">{f === "SHIP" ? "Ship to me" : "Pick up in store"}</p>
                <p className="text-neutral-600">{f === "SHIP" ? "Standard or express" : "Free, usually ready in 1-4 hours"}</p>
              </button>
            ))}
          </div>
          {fulfillment === "SHIP" ? (
            <div className="space-y-3">
              {field("name", "Full name", { required: true, autoComplete: "name" })}
              {field("line1", "Address", { required: true, autoComplete: "address-line1" })}
              {field("line2", "Apt, suite (optional)", { autoComplete: "address-line2" })}
              <div className="grid grid-cols-3 gap-3">
                {field("city", "City", { required: true })}
                <label className="block">
                  <span className="label">State</span>
                  <select className="input" value={addr.state} onChange={(e) => setAddr({ ...addr, state: e.target.value })} data-testid="ship-state">
                    {STATES.map((s) => <option key={s}>{s}</option>)}
                  </select>
                </label>
                {field("zip", "ZIP", { required: true, pattern: "\\d{5}", inputMode: "numeric" })}
              </div>
              <div className="space-y-2">
                <p className="label">Shipping method</p>
                {([["STANDARD", "Standard (5-7 business days)", bag.merchandiseCents >= bag.freeShippingThresholdCents ? "Free" : "$7.99"], ["EXPRESS", "Express (2 business days)", "$19.99"]] as const).map(([m, label, price]) => (
                  <label key={m} className={`flex cursor-pointer items-center justify-between border p-3 text-sm ${method === m ? "border-teal" : "border-neutral-300"}`}>
                    <span className="flex items-center gap-2"><input type="radio" name="method" checked={method === m} onChange={() => setMethod(m)} data-testid={`method-${m}`} />{label}</span>
                    <span>{price}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {store && <p className="bg-teal-light p-3 text-sm" data-testid="pickup-store">Pick up at <span className="font-semibold">{store.name}</span>, {store.address}, {store.city}. Ready in about {store.pickupReadyHours} hr.</p>}
              <StoreSearch selected={store?.id} onSelect={setStore} />
            </div>
          )}
          <label className="block">
            <span className="label">Phone (optional, for delivery updates)</span>
            <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" />
          </label>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">3. Payment</h2>
          <p className="bg-sand p-3 text-xs text-neutral-700">
            Demo store, no real charges. Test cards: <code>4242 4242 4242 4242</code> approves, <code>4000 0000 0000 0002</code> is declined. Use any future expiry and any 3-digit CVC.
          </p>
          <label className="block"><span className="label">Name on card</span><input required className="input" value={card.name} onChange={(e) => setCard({ ...card, name: e.target.value })} data-testid="card-name" /></label>
          <label className="block"><span className="label">Card number</span><input required className="input font-mono" inputMode="numeric" autoComplete="cc-number" value={card.number} onChange={(e) => setCard({ ...card, number: e.target.value })} data-testid="card-number" /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block"><span className="label">Expiry (MM/YY)</span><input required className="input" placeholder="12/30" value={card.exp} onChange={(e) => setCard({ ...card, exp: e.target.value })} data-testid="card-exp" /></label>
            <label className="block"><span className="label">CVC</span><input required className="input" inputMode="numeric" value={card.cvc} onChange={(e) => setCard({ ...card, cvc: e.target.value })} data-testid="card-cvc" /></label>
          </div>
        </section>
        {error && <p className="border border-sale bg-red-50 p-3 text-sm text-sale" role="alert" data-testid="checkout-error">{error}</p>}
      </div>

      <aside className="h-fit space-y-4 bg-sand p-6 md:sticky md:top-4">
        <h2 className="text-lg font-semibold">Order summary</h2>
        <ul className="space-y-3 text-sm">
          {bag.items.map((l) => (
            <li key={l.sku} className="flex justify-between gap-3">
              <span>{l.name} <span className="text-neutral-500">· {l.color} · {l.size} × {l.quantity}</span></span>
              <span>{money(l.lineSubtotalCents)}</span>
            </li>
          ))}
        </ul>
        {t ? (
          <dl className="space-y-2 border-t pt-3 text-sm" data-testid="quote">
            <div className="flex justify-between"><dt>Subtotal</dt><dd>{money(t.subtotalCents)}</dd></div>
            {t.discountCents > 0 && <div className="flex justify-between text-sale"><dt>Promo {bag.promoCode}</dt><dd>−{money(t.discountCents)}</dd></div>}
            <div className="flex justify-between"><dt>{fulfillment === "PICKUP" ? "Pickup" : "Shipping"}</dt><dd>{t.shippingCents === 0 ? "Free" : money(t.shippingCents)}</dd></div>
            {t.fees.map((f) => <div key={f.code} className="flex justify-between"><dt>{f.label}</dt><dd>{money(f.amountCents)}</dd></div>)}
            <div className="flex justify-between"><dt>Tax ({Number(t.taxRate).toFixed(2)}%)</dt><dd>{money(t.taxCents)}</dd></div>
            <div className="flex justify-between border-t pt-2 text-base font-semibold"><dt>Total</dt><dd data-testid="order-total">{money(t.totalCents)}</dd></div>
          </dl>
        ) : (
          <p className="text-sm text-neutral-600">{fulfillment === "PICKUP" ? "Choose a store to see your total." : "Calculating..."}</p>
        )}
        <button type="submit" disabled={placing || !t} className="btn w-full" data-testid="place-order">{placing ? "Placing order..." : "Place order"}</button>
      </aside>
    </form>
  );
}
