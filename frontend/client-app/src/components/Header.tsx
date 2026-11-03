"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { departments } from "@/config/site";
import { useBag } from "./BagProvider";

export function Header() {
  const { bag, customer, setDrawerOpen } = useBag();
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const router = useRouter();
  const active = departments.find((d) => d.slug === open);

  return (
    <header className="relative z-30 border-b border-neutral-200 bg-white" onMouseLeave={() => setOpen(null)}>
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
        <Link href="/" className="font-display text-2xl font-bold tracking-tight text-teal" aria-label="OtterShops home">OtterShops</Link>
        <form
          className="hidden flex-1 md:block"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
          }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search dresses, jeans, hoodies..."
            aria-label="Search"
            className="w-full max-w-md rounded-full border border-neutral-300 px-4 py-2 text-sm focus:border-teal focus:outline-none"
          />
        </form>
        <nav className="ml-auto flex items-center gap-5 text-sm">
          <Link href="/stores" className="hover:underline">Find a store</Link>
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
      <nav className="mx-auto flex max-w-7xl gap-6 px-4 text-sm font-semibold" aria-label="Departments">
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
