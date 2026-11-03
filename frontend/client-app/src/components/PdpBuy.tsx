"use client";

import { useMemo, useState } from "react";
import { HttpError } from "@/lib/client";
import { sizeRank } from "@/lib/format";
import type { ProductDetail } from "@/lib/types";
import { useBag } from "./BagProvider";
import { FavoriteButton } from "./FavoritesProvider";
import { Modal } from "./Modal";
import { NotifyMe } from "./NotifyMe";
import { Price } from "./Price";
import { SizeChart } from "./SizeChart";
import { StoreAvailabilityModal } from "./StoreAvailabilityModal";

export function PdpBuy({ p }: { p: ProductDetail }) {
  const { add } = useBag();
  const firstColor = p.colors.find((c) => !c.soldOut)?.name ?? p.colors[0]?.name ?? "";
  const [color, setColor] = useState(firstColor);
  const [size, setSize] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageIdx, setImageIdx] = useState(0);
  const [sizeGuide, setSizeGuide] = useState(false);
  const [stores, setStores] = useState(false);

  const gallery = useMemo(() => {
    const own = p.images.filter((i) => i.color === color);
    const shared = p.images.filter((i) => i.color === null);
    const rest = p.images.filter((i) => i.color !== null && i.color !== color);
    return [...own, ...shared, ...rest];
  }, [p.images, color]);

  const skus = p.skus.filter((s) => s.color === color).sort((a, b) => sizeRank(a.size) - sizeRank(b.size));
  const chosen = skus.find((s) => s.size === size) ?? null;
  const main = gallery[Math.min(imageIdx, gallery.length - 1)];

  async function onAdd() {
    if (!chosen) {
      setError("Select a size.");
      return;
    }
    if (chosen.soldOut) return;
    setBusy(true);
    setError(null);
    try {
      await add(chosen.sku, qty);
    } catch (e) {
      setError(e instanceof HttpError ? e.message : "Could not add to bag.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-10 md:grid-cols-[1fr_420px]">
      <div className="grid grid-cols-[72px_1fr] gap-3" data-testid="gallery">
        <div className="space-y-2">
          {gallery.map((img, i) => (
            <button key={img.url + i} type="button" onClick={() => setImageIdx(i)} className={`block border-2 ${i === imageIdx ? "border-ink" : "border-transparent"}`} aria-label={`View image ${i + 1}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.url.replace(".webp", "-sm.webp")} alt="" className="aspect-[4/5] w-full object-cover" />
            </button>
          ))}
        </div>
        <div className="group relative overflow-hidden bg-sand">
          {main && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={main.url} alt={main.alt} data-testid="main-image" className="aspect-[4/5] w-full object-cover transition-transform duration-300 group-hover:scale-125" />
          )}
        </div>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-neutral-500">{p.label}</p>
        <div className="mt-1 flex items-start justify-between gap-3">
          <h1 className="font-display text-3xl font-bold" data-testid="pdp-name">{p.name}</h1>
          <FavoriteButton productId={p.id} color={color} name={p.name} className="shrink-0 border" />
        </div>
        {p.reviewCount > 0 && (
          <a href="#reviews" className="mt-1 inline-block text-sm text-neutral-600 hover:underline" data-testid="rating-link">
            <span aria-hidden="true">★ {p.rating.toFixed(1)}</span><span className="sr-only">Rated {p.rating.toFixed(1)} out of 5.</span> · {p.reviewCount} reviews
          </a>
        )}
        <div className="mt-4"><Price price={p.price} size="lg" /></div>
        {p.price.excludedFromPromo && <p className="mt-1 text-xs text-neutral-500" data-testid="excluded-note">Excluded from promotion</p>}

        <div className="mt-6">
          <p className="text-sm"><span className="font-semibold">Color:</span> <span data-testid="selected-color">{color}</span></p>
          <div className="mt-2 flex flex-wrap gap-2">
            {p.colors.map((c) => (
              <button
                key={c.name}
                type="button"
                title={c.name}
                aria-label={c.name}
                aria-pressed={c.name === color}
                data-testid={`swatch-${c.name}`}
                onClick={() => { setColor(c.name); setSize(null); setImageIdx(0); setError(null); }}
                className={`relative h-9 w-9 rounded-full border-2 ${c.name === color ? "border-ink" : "border-neutral-200"} ${c.soldOut ? "opacity-40" : ""}`}
                style={{ background: c.hex }}
              />
            ))}
          </div>
        </div>

        <div className="mt-6">
          <div className="flex items-baseline justify-between">
            <p className="text-sm font-semibold" id="size-label">Size{chosen && <span className="font-normal">: {chosen.size}</span>}</p>
            <button type="button" className="text-sm underline" onClick={() => setSizeGuide(true)} data-testid="size-guide-link">Size guide</button>
          </div>
          <div className="mt-2 grid grid-cols-5 gap-2" role="group" aria-labelledby="size-label">
            {skus.map((s) => (
              <button
                key={s.sku}
                type="button"
                aria-pressed={s.size === size}
                aria-label={s.soldOut ? `${s.size}, sold out. Choose to get a back-in-stock alert` : s.size}
                data-testid={`size-${s.size}`}
                data-available={!s.soldOut}
                onClick={() => { setSize(s.size); setQty(1); setError(null); }}
                className={`border py-2 text-sm ${s.size === size ? (s.soldOut ? "border-ink text-neutral-500 line-through" : "border-ink bg-ink text-white") : s.soldOut ? "border-dashed border-neutral-300 text-neutral-400 line-through hover:border-ink" : "border-neutral-300 hover:border-ink"}`}
              >
                {s.size}
              </button>
            ))}
          </div>
          {chosen?.lowStock && <p className="mt-2 text-sm font-semibold text-sale" data-testid="only-n-left">Only {chosen.stock} left</p>}
          {skus.every((s) => s.soldOut) && <p className="mt-2 text-sm text-neutral-600">This color is sold out. Try another color, or pick a size to get an alert.</p>}
        </div>

        {chosen?.soldOut ? (
          <NotifyMe key={chosen.sku} sku={chosen.sku} label={`${p.name} in ${chosen.color}, size ${chosen.size}`} />
        ) : (
          <>

        <div className="mt-6 flex items-center gap-3">
          <label className="text-sm font-semibold" htmlFor="qty">Qty</label>
          <select id="qty" value={qty} onChange={(e) => setQty(Number(e.target.value))} className="border border-neutral-300 px-2 py-2" data-testid="qty">
            {Array.from({ length: Math.max(1, Math.min(10, chosen?.stock ?? 10)) }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <button type="button" onClick={onAdd} disabled={busy || p.stockState === "SOLD_OUT"} className="btn flex-1" data-testid="add-to-bag">
            {p.stockState === "SOLD_OUT" ? "Sold out" : busy ? "Adding..." : "Add to Bag"}
          </button>
        </div>
          </>
        )}
        {error && <p className="mt-2 text-sm text-sale" role="alert">{error}</p>}
        <div className="mt-4 flex items-center justify-between border p-3 text-sm">
          <div>
            <p className="font-semibold">Free pickup in store</p>
            <p className="text-xs text-neutral-600">{chosen ? "See which stores have your size." : "Choose a size to check stores near you."}</p>
          </div>
          <button type="button" className="underline disabled:opacity-50" disabled={!chosen} onClick={() => setStores(true)} data-testid="check-stores">Check stores</button>
        </div>
        <p className="mt-3 text-xs text-neutral-600">Free standard shipping on $50+. Free returns within 45 days.</p>

        <div className="mt-8 divide-y border-y text-sm">
          <details open className="py-3">
            <summary className="cursor-pointer font-semibold">Details</summary>
            <p className="mt-2 text-neutral-700">{p.description}</p>
            <ul className="mt-2 list-disc pl-5 text-neutral-700">{p.details.split("\n").map((d) => <li key={d}>{d}</li>)}</ul>
          </details>
          <details className="py-3">
            <summary className="cursor-pointer font-semibold">Materials &amp; care</summary>
            <p className="mt-2 text-neutral-700">{p.materials}. Machine wash cold with like colors.</p>
          </details>
          <details className="py-3">
            <summary className="cursor-pointer font-semibold">Shipping &amp; returns</summary>
            <p className="mt-2 text-neutral-700">Standard shipping is free on orders of $50 or more. Return anything within 45 days by mail or in store.</p>
          </details>
        </div>
      </div>
      {sizeGuide && (
        <Modal title="Size guide" onClose={() => setSizeGuide(false)} testId="size-guide" wide>
          {p.fit && <p className="mb-4 text-sm"><span className="font-semibold">Fit:</span> {p.fit}</p>}
          <SizeChart department={p.department} />
        </Modal>
      )}
      {stores && chosen && (
        <StoreAvailabilityModal productId={p.id} sku={chosen.sku} label={`${p.name} · ${chosen.color} · ${chosen.size}`} onClose={() => setStores(false)} />
      )}
    </div>
  );
}
