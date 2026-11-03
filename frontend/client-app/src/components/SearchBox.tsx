"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { call } from "@/lib/client";
import { money } from "@/lib/format";
import type { SuggestResult } from "@/lib/types";

const POPULAR = ["jeans", "sweaters", "hoodies", "dresses", "puffer"];

/** Header search with typeahead (combobox pattern: arrow keys, Enter, Escape). */
export function SearchBox({ onNavigate, className = "" }: { onNavigate?: () => void; className?: string }) {
  const router = useRouter();
  const listId = useId();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<SuggestResult | null>(null);
  const [active, setActive] = useState(-1);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) { setResult(null); return; }
    const t = setTimeout(async () => {
      try { setResult(await call<SuggestResult>(`/search/suggest?q=${encodeURIComponent(term)}`)); setActive(-1); } catch { /* keep last */ }
    }, 150);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const options: { href: string; key: string }[] = result
    ? [...result.terms.map((t) => ({ href: t.href, key: `t-${t.href}` })), ...result.products.map((p) => ({ href: `/p/${p.id}`, key: `p-${p.id}` }))]
    : [];

  const go = (href: string) => {
    setOpen(false);
    onNavigate?.();
    router.push(href);
  };

  return (
    <div ref={wrap} className={`relative ${className}`}>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          if (active >= 0 && options[active]) return go(options[active].href);
          if (q.trim()) go(`/search?q=${encodeURIComponent(q.trim())}`);
        }}
      >
        <label htmlFor={`${listId}-input`} className="sr-only">Search</label>
        <input
          id={`${listId}-input`}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, options.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, -1)); }
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Search dresses, jeans, hoodies..."
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 && options[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          className="w-full rounded-full border border-neutral-300 px-4 py-2 text-sm focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/30"
          data-testid="search-input"
        />
      </form>
      {open && (
        <div id={listId} role="listbox" aria-label="Search suggestions" className="absolute left-0 right-0 top-full z-40 mt-2 rounded-lg border bg-white p-3 shadow-xl" data-testid="search-suggestions">
          {!result ? (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Popular searches</p>
              <div className="flex flex-wrap gap-2">
                {POPULAR.map((p) => (
                  <button key={p} type="button" onClick={() => go(`/search?q=${p}`)} className="rounded-full border px-3 py-1 text-sm hover:border-teal">{p}</button>
                ))}
              </div>
            </div>
          ) : result.totalProducts === 0 ? (
            <p className="text-sm text-neutral-600">No matches for &ldquo;{result.query}&rdquo;. Try a broader word like &ldquo;tee&rdquo; or &ldquo;jacket&rdquo;.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-[1fr_2fr]">
              <ul className="space-y-1 text-sm">
                {result.terms.map((t, i) => (
                  <li key={t.href} id={`${listId}-${i}`} role="option" aria-selected={active === i}>
                    <Link href={t.href} onClick={() => go(t.href)} className={`block rounded px-2 py-1 hover:bg-sand ${active === i ? "bg-sand" : ""}`}>{t.label}</Link>
                  </li>
                ))}
              </ul>
              <ul className="space-y-2">
                {result.products.map((p, j) => {
                  const i = result.terms.length + j;
                  return (
                    <li key={p.id} id={`${listId}-${i}`} role="option" aria-selected={active === i}>
                      <Link href={`/p/${p.id}`} onClick={() => go(`/p/${p.id}`)} className={`flex items-center gap-3 rounded p-1 hover:bg-sand ${active === i ? "bg-sand" : ""}`} data-testid="suggest-product">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        {p.image && <img src={p.image.replace(".webp", "-sm.webp")} alt="" className="h-12 w-10 object-cover" />}
                        <span className="flex-1 text-sm">{p.name}</span>
                        <span className={`text-sm ${p.price.onSale ? "text-sale" : ""}`}>{money(p.price.priceCents)}</span>
                      </Link>
                    </li>
                  );
                })}
                <li>
                  <button type="button" onClick={() => go(`/search?q=${encodeURIComponent(q.trim())}`)} className="text-sm font-semibold text-teal underline" data-testid="suggest-all">
                    See all {result.totalProducts} results
                  </button>
                </li>
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
