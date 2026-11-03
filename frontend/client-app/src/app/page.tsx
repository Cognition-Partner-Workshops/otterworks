import Link from "next/link";
import { Countdown } from "@/components/Countdown";
import { ProductCard } from "@/components/ProductCard";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

const TILES = [
  { label: "Women", href: "/c/women", image: "/images/editorial/editorial-10.webp" },
  { label: "Men", href: "/c/men", image: "/images/editorial/editorial-21.webp" },
  { label: "Kids", href: "/c/kids", image: "/images/editorial/editorial-14.webp" },
  { label: "Baby", href: "/c/baby", image: "/images/editorial/editorial-15.webp" },
];

export default async function Home() {
  const [promo, doorbusters, arrivals, denim] = await Promise.all([
    api.promotion(),
    api.products({ onSale: "true", sort: "discount", pageSize: "8" }),
    api.products({ collection: "new-arrivals", sort: "newest", pageSize: "8" }),
    api.products({ collection: "denim", pageSize: "4" }),
  ]);
  const live = promo?.active && promo.endsAt;

  return (
    <div>
      <section className="relative isolate overflow-hidden bg-ink text-white" data-testid="hero">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/images/editorial/editorial-04.webp" alt="" className="absolute inset-0 -z-10 h-full w-full object-cover opacity-50" />
        <div className="mx-auto max-w-7xl px-4 py-24 md:py-32">
          {live ? (
            <>
              <p className="text-sm font-semibold uppercase tracking-[0.2em]">{promo.name}</p>
              <h1 className="mt-3 max-w-2xl font-display text-5xl font-bold md:text-6xl">{promo.headline}</h1>
              <p className="mt-4 max-w-xl text-lg">{promo.subhead}</p>
              <Countdown endsAt={promo.endsAt!} className="mt-6 inline-block bg-white/15 px-4 py-2 font-mono text-lg" />
              <div className="mt-8 flex gap-3">
                <Link href="/sale" className="btn bg-sale hover:bg-red-800">Shop the sale</Link>
                <Link href="/c/new-arrivals" className="btn-outline border-white">New arrivals</Link>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold uppercase tracking-[0.2em]">Just landed</p>
              <h1 className="mt-3 max-w-2xl font-display text-5xl font-bold md:text-6xl">New arrivals for every day</h1>
              <p className="mt-4 max-w-xl text-lg">Soft knits, easy denim and layers for the whole family.</p>
              <div className="mt-8"><Link href="/c/new-arrivals" className="btn">Shop new arrivals</Link></div>
            </>
          )}
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl grid-cols-2 gap-4 px-4 py-10 md:grid-cols-4">
        {TILES.map((t) => (
          <Link key={t.label} href={t.href} className="group relative block aspect-[3/4] overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={t.image} alt="" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
            <span className="absolute bottom-4 left-4 bg-white px-4 py-2 font-semibold">{t.label}</span>
          </Link>
        ))}
      </section>

      {live && doorbusters.items.length > 0 && (
        <Rail title="Doorbusters" href="/sale?sort=discount" items={doorbusters.items} testid="doorbusters" />
      )}
      <Rail title="New arrivals" href="/c/new-arrivals" items={arrivals.items} testid="new-arrivals" />

      <section className="mx-auto mt-12 grid max-w-7xl items-center gap-8 bg-sand px-4 py-10 md:grid-cols-2">
        <div className="px-4">
          <p className="text-sm font-semibold uppercase tracking-wide text-teal">Riverbend Denim</p>
          <h2 className="mt-2 font-display text-4xl font-bold">Every fit. Every wash.</h2>
          <p className="mt-3 text-neutral-700">Skinny to wide-leg, light wash to black. Stretch that keeps its shape all day.</p>
          <Link href="/c/denim" className="btn mt-6">Shop denim</Link>
        </div>
        <div className="grid grid-cols-2 gap-4">{denim.items.map((p) => <ProductCard key={p.id} p={p} />)}</div>
      </section>

      <section className="mx-auto mt-12 max-w-7xl px-4">
        <div className="flex flex-col items-start justify-between gap-4 bg-teal px-8 py-10 text-white md:flex-row md:items-center">
          <div>
            <h2 className="font-display text-3xl font-bold">OtterShops Rewards</h2>
            <p className="mt-2">Earn 1 point for every $1. Members get early access to sales.</p>
          </div>
          <Link href="/account/register" className="btn-outline border-white">Join for free</Link>
        </div>
      </section>
    </div>
  );
}

function Rail({ title, href, items, testid }: { title: string; href: string; items: import("@/lib/types").ProductCard[]; testid: string }) {
  return (
    <section className="mx-auto mt-10 max-w-7xl px-4" data-testid={testid}>
      <div className="mb-4 flex items-end justify-between">
        <h2 className="font-display text-2xl font-bold">{title}</h2>
        <Link href={href} className="text-sm underline">Shop all</Link>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{items.slice(0, 8).map((p) => <ProductCard key={p.id} p={p} />)}</div>
    </section>
  );
}
