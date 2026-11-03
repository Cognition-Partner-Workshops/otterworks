"use client";

import Link from "next/link";
import { money } from "@/lib/format";
import { useBag } from "./BagProvider";
import { FreeShippingBar } from "./FreeShippingBar";

export function MiniBag() {
  const { bag, drawerOpen, setDrawerOpen } = useBag();
  if (!drawerOpen) return null;
  const items = bag?.items ?? [];
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Your bag">
      <button type="button" aria-label="Close bag" className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col bg-white shadow-xl" data-testid="mini-bag">
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="text-lg font-semibold">Your bag ({bag?.itemCount ?? 0})</h2>
          <button type="button" onClick={() => setDrawerOpen(false)} className="text-2xl leading-none" aria-label="Close">×</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {items.length === 0 ? (
            <p className="text-sm text-neutral-600">Your bag is empty.</p>
          ) : (
            <ul className="space-y-4">
              {items.map((l) => (
                <li key={l.sku} className="flex gap-3" data-testid="mini-bag-line">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {l.image && <img src={l.image.replace(".webp", "-sm.webp")} alt="" className="h-24 w-20 object-cover" />}
                  <div className="text-sm">
                    <p className="font-medium">{l.name}</p>
                    <p className="text-neutral-600">{l.color} · {l.size} · Qty {l.quantity}</p>
                    <p className={l.unitPriceCents < l.unitListCents ? "text-sale" : ""}>{money(l.lineSubtotalCents)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        {bag && items.length > 0 && (
          <div className="space-y-3 border-t p-4">
            <FreeShippingBar bag={bag} />
            <div className="flex justify-between font-semibold"><span>Subtotal</span><span>{money(bag.merchandiseCents)}</span></div>
            <Link href="/bag" onClick={() => setDrawerOpen(false)} className="block bg-teal py-3 text-center font-semibold text-white hover:bg-teal-dark" data-testid="view-bag">
              View bag &amp; check out
            </Link>
          </div>
        )}
      </aside>
    </div>
  );
}
