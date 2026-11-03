import Link from "next/link";
import { FavoriteButton } from "./FavoritesProvider";
import { Price } from "./Price";
import { QuickAdd } from "./QuickAdd";
import type { ProductCard as Card } from "@/lib/types";

export function ProductCard({ p }: { p: Card }) {
  return (
    <div className="group relative" data-testid="product-card">
    <Link href={`/p/${p.id}`} className="block">
      <div className="relative aspect-[4/5] overflow-hidden bg-sand">
        {p.image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={p.image} alt={p.name} loading="lazy" className="absolute inset-0 h-full w-full object-cover transition-opacity duration-300 group-hover:opacity-0" />
        )}
        {p.hoverImage && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={p.hoverImage} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        )}
        <div className="absolute left-2 top-2 flex flex-col gap-1">
          {p.stockState === "SOLD_OUT" && <span className="bg-ink px-2 py-0.5 text-[11px] font-semibold uppercase text-white">Sold out</span>}
          {p.stockState === "LOW_STOCK" && <span className="bg-white px-2 py-0.5 text-[11px] font-semibold uppercase text-sale">Low stock</span>}
          {p.isNew && p.stockState !== "SOLD_OUT" && <span className="bg-teal px-2 py-0.5 text-[11px] font-semibold uppercase text-white">New</span>}
        </div>
      </div>
      <div className="mt-2 space-y-1">
        <div className="flex gap-1">
          {p.colors.slice(0, 5).map((c) => (
            <span key={c.name} title={c.name} aria-hidden="true" className="h-3 w-3 rounded-full border border-neutral-300" style={{ background: c.hex }} />
          ))}
        </div>
        <p className="text-xs uppercase tracking-wide text-neutral-500">{p.label}</p>
        <p className="text-sm leading-snug group-hover:underline">{p.name}</p>
        <Price price={p.price} />
        {p.reviewCount > 0 && <p className="text-xs text-neutral-500"><span aria-hidden="true">★ {p.rating.toFixed(1)} ({p.reviewCount})</span><span className="sr-only">Rated {p.rating.toFixed(1)} out of 5 from {p.reviewCount} reviews</span></p>}
      </div>
    </Link>
    <FavoriteButton productId={p.id} name={p.name} className="absolute right-2 top-2" />
    {p.stockState !== "SOLD_OUT" && <QuickAdd productId={p.id} name={p.name} />}
    </div>
  );
}
