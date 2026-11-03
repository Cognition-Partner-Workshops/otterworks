"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { departments } from "@/config/site";
import { useBag } from "./BagProvider";

/** Slide-in department menu for small screens; Escape or the backdrop closes it and focus returns to the trigger. */
export function MobileNav({ onClose }: { onClose: () => void }) {
  const { customer } = useBag();
  const [open, setOpen] = useState<string | null>(null);
  const first = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    first.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus();
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Menu" id="mobile-nav">
      <button type="button" aria-label="Close menu" className="absolute inset-0 bg-black/40" onClick={onClose} tabIndex={-1} />
      <nav className="absolute left-0 top-0 flex h-full w-[85%] max-w-sm flex-col overflow-y-auto bg-white shadow-xl" aria-label="Mobile" data-testid="mobile-nav">
        <div className="flex items-center justify-between border-b p-4">
          <span className="font-display text-xl font-bold text-teal">OtterShops</span>
          <button ref={first} type="button" onClick={onClose} className="text-2xl leading-none" aria-label="Close menu">×</button>
        </div>
        <ul className="divide-y">
          {departments.map((d) => (
            <li key={d.slug}>
              <button
                type="button"
                className={`flex w-full items-center justify-between px-4 py-3 text-left font-semibold ${d.slug === "sale" ? "text-sale" : ""}`}
                aria-expanded={open === d.slug}
                onClick={() => setOpen(open === d.slug ? null : d.slug)}
                data-testid={`mobile-dept-${d.slug}`}
              >
                {d.label}<span aria-hidden="true">{open === d.slug ? "−" : "+"}</span>
              </button>
              {open === d.slug && (
                <ul className="bg-sand/50 px-4 pb-3 text-sm">
                  <li><Link href={d.href} onClick={onClose} className="block py-2 font-semibold underline">Shop all {d.label}</Link></li>
                  {d.columns.flatMap((c) => c.links).slice(0, 12).map((l) => (
                    <li key={l.href}><Link href={l.href} onClick={onClose} className="block py-2">{l.label}</Link></li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
        <ul className="mt-auto space-y-3 border-t p-4 text-sm">
          <li><Link href={customer ? "/account" : "/account/sign-in"} onClick={onClose}>{customer ? `My account (${customer.firstName})` : "Sign in or create account"}</Link></li>
          <li><Link href="/favorites" onClick={onClose}>Favorites</Link></li>
          <li><Link href="/stores" onClick={onClose}>Find a store</Link></li>
          <li><Link href="/order-lookup" onClick={onClose}>Track an order</Link></li>
          <li><Link href="/help" onClick={onClose}>Help</Link></li>
        </ul>
      </nav>
    </div>
  );
}
