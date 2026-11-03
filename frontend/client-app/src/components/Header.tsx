"use client";

import Link from "next/link";
import { useState } from "react";
import { departments } from "@/config/site";
import { useBag } from "./BagProvider";
import { useFavorites } from "./FavoritesProvider";
import { MobileNav } from "./MobileNav";
import { SearchBox } from "./SearchBox";

export function Header() {
  const { bag, customer, setDrawerOpen } = useBag();
  const [open, setOpen] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const { wishlist } = useFavorites();
  const active = departments.find((d) => d.slug === open);

  return (
    <header className="relative z-30 border-b border-neutral-200 bg-white" onMouseLeave={() => setOpen(null)}>
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 md:gap-6">
        <Link href="/" className="font-display text-2xl font-bold tracking-tight text-teal" aria-label="OtterShops home">OtterShops</Link>
        <button
          type="button"
          className="order-first -ml-1 p-2 md:hidden"
          aria-label="Open menu"
          aria-expanded={menu}
          aria-controls="mobile-nav"
          onClick={() => setMenu(true)}
          data-testid="mobile-menu-button"
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6 stroke-ink" strokeWidth="2" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
        </button>
        <SearchBox className="hidden max-w-md flex-1 md:block" />
        <nav className="ml-auto flex items-center gap-5 text-sm">
          <Link href="/stores" className="hidden hover:underline sm:inline">Find a store</Link>
          <Link href="/favorites" className="relative hover:underline" aria-label={`Favorites (${wishlist?.count ?? 0})`} data-testid="favorites-link">
            <span aria-hidden="true">&#9825;</span><span className="ml-1 hidden lg:inline">Favorites</span>
            {!!wishlist?.count && <span className="ml-1 text-xs text-sale" data-testid="favorites-count">{wishlist.count}</span>}
          </Link>
          <Link href={customer ? "/account" : "/account/sign-in"} className="hover:underline" data-testid="account-link">
            {customer ? `Hi, ${customer.firstName}` : "Sign in"}
          </Link>
          <button type="button" onClick={() => setDrawerOpen(true)} className="relative font-semibold" aria-label="Open bag" data-testid="bag-button">
            Bag
            <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-teal px-1 text-xs text-white" data-testid="bag-count">
              {bag?.itemCount ?? 0}
            </span>
          </button>
        </nav>
      </div>
      <div className="px-4 pb-3 md:hidden"><SearchBox /></div>
      <nav className="mx-auto hidden max-w-7xl gap-6 px-4 text-sm font-semibold md:flex" aria-label="Departments">
        {departments.map((d) => (
          <Link
            key={d.slug}
            href={d.href}
            onMouseEnter={() => setOpen(d.slug)}
            onFocus={() => setOpen(d.slug)}
            onClick={() => setOpen(null)}
            className={`border-b-2 py-3 ${open === d.slug ? "border-teal" : "border-transparent"} ${d.slug === "sale" ? "text-sale" : ""}`}
            data-testid={`dept-${d.slug}`}
          >
            {d.label}
          </Link>
        ))}
      </nav>
      {menu && <MobileNav onClose={() => setMenu(false)} />}
      {active && (
        <div className="absolute inset-x-0 top-full border-b border-neutral-200 bg-white shadow-lg" data-testid="mega-menu">
          <div className="mx-auto grid max-w-7xl grid-cols-4 gap-8 px-4 py-8">
            {active.columns.map((col) => (
              <div key={col.title}>
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">{col.title}</p>
                <ul className="space-y-2 text-sm">
                  {col.links.map((l) => (
                    <li key={l.href}><Link href={l.href} onClick={() => setOpen(null)} className="hover:underline">{l.label}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
            {active.feature && (
              <Link href={active.feature.href} onClick={() => setOpen(null)} className="col-start-4 block">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={active.feature.image} alt="" className="aspect-[4/3] w-full object-cover" />
                <p className="mt-2 text-sm font-semibold">{active.feature.title}</p>
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
