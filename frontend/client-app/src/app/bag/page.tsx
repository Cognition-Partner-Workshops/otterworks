"use client";

import Link from "next/link";
import { useState } from "react";
import { useBag } from "@/components/BagProvider";
import { HttpError } from "@/lib/client";
import { money } from "@/lib/format";

export default function BagPage() {
  const { bag, ready, setQuantity, remove, applyPromo, removePromo } = useBag();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return <div className="mx-auto max-w-5xl px-4 py-10">Loading your bag...</div>;
  if (!bag || bag.items.length === 0) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center">
        <h1 className="font-display text-3xl font-bold">Your bag is empty</h1>
        <Link href="/c/new-arrivals" className="btn mt-6">Shop new arrivals</Link>
      </div>
    );
  }
  const savings = bag.listSubtotalCents - bag.merchandiseCents;

  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-4 py-8 md:grid-cols-[1fr_360px]">
      <section>
        <h1 className="font-display text-3xl font-bold">Bag ({bag.itemCount})</h1>
        <ul className="mt-6 divide-y border-y">
          {bag.items.map((l) => (
            <li key={l.sku} className="flex gap-4 py-4" data-testid="bag-line">
              <Link href={`/p/${l.productId}`} className="shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {l.image && <img src={l.image.replace(".webp", "-sm.webp")} alt={l.name} className="h-32 w-24 object-cover" />}
              </Link>
              <div className="flex flex-1 flex-col gap-1 text-sm">
                <Link href={`/p/${l.productId}`} className="font-semibold hover:underline">{l.name}</Link>
                <p className="text-neutral-600">{l.color} · Size {l.size}</p>
                {l.excludedFromPromo && <p className="text-xs text-neutral-500">Excluded from promotion</p>}
                {l.stock <= 5 && <p className="text-xs font-semibold text-sale">Only {l.stock} left</p>}
                <div className="mt-auto flex items-center gap-3">
                  <div className="flex items-center border">
                    <button type="button" aria-label="Decrease quantity" disabled={busy || l.quantity <= 1} onClick={() => run(() => setQuantity(l.sku, l.quantity - 1))} className="px-3 py-1 disabled:opacity-30">−</button>
                    <span className="w-8 text-center" data-testid="line-qty">{l.quantity}</span>
                    <button type="button" aria-label="Increase quantity" disabled={busy} onClick={() => run(() => setQuantity(l.sku, l.quantity + 1))} className="px-3 py-1 disabled:opacity-30">+</button>
                  </div>
                  <button type="button" onClick={() => run(() => remove(l.sku))} className="text-xs underline" data-testid="remove-line">Remove</button>
                </div>
              </div>
              <div className="text-right text-sm">
                <p className={l.unitPriceCents < l.unitListCents ? "font-semibold text-sale" : "font-semibold"}>{money(l.lineSubtotalCents)}</p>
                {l.unitPriceCents < l.unitListCents && <s className="text-xs text-neutral-500">{money(l.unitListCents * l.quantity)}</s>}
                {l.discountCents > 0 && <p className="text-xs text-teal">−{money(l.discountCents)} code</p>}
              </div>
            </li>
          ))}
        </ul>
        {error && <p className="mt-3 text-sm text-sale" role="alert">{error}</p>}
      </section>

      <aside className="h-fit space-y-4 bg-sand p-6">
        <h2 className="text-lg font-semibold">Order summary</h2>
        {bag.promoCode ? (
          <div className="flex items-center justify-between bg-white p-3 text-sm" data-testid="applied-promo">
            <span><span className="font-semibold">{bag.promoCode}</span> {bag.promoDescription && `· ${bag.promoDescription}`}</span>
            <button type="button" onClick={() => run(removePromo)} className="text-xs underline">Remove</button>
          </div>
        ) : (
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (code.trim()) void run(async () => { await applyPromo(code.trim()); setCode(""); });
            }}
          >
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Promo code" aria-label="Promo code" className="input bg-white" data-testid="promo-input" />
            <button type="submit" disabled={busy} className="btn-outline px-4 py-2 text-sm" data-testid="promo-apply">Apply</button>
          </form>
        )}
        {bag.promoError && <p className="text-sm text-sale" role="alert">{bag.promoError}</p>}
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between"><dt>Subtotal</dt><dd>{money(bag.listSubtotalCents)}</dd></div>
          {savings > 0 && <div className="flex justify-between text-sale"><dt>Savings</dt><dd>−{money(savings)}</dd></div>}
          <div className="flex justify-between"><dt>Shipping</dt><dd>{bag.freeShippingRemainingCents === 0 ? "Free" : "Calculated at checkout"}</dd></div>
          <div className="flex justify-between border-t pt-2 text-base font-semibold"><dt>Estimated total</dt><dd data-testid="bag-total">{money(bag.merchandiseCents)}</dd></div>
        </dl>
        {bag.freeShippingRemainingCents > 0 && <p className="text-xs">Add {money(bag.freeShippingRemainingCents)} more for free standard shipping.</p>}
        <Link href="/checkout" className="btn w-full" data-testid="checkout-button">Checkout</Link>
        <p className="text-xs text-neutral-500">Tax is calculated at checkout.</p>
      </aside>
    </div>
  );
}
