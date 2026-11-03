"use client";

import { useState } from "react";
import { StoreSearch } from "@/components/StoreSearch";

export default function StoresPage() {
  const [mine, setMine] = useState<string | null>(() => (typeof window === "undefined" ? null : localStorage.getItem("os_store")));
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-3xl font-bold">Find a store</h1>
      <p className="mt-2 text-sm text-neutral-600">Search by ZIP code or city. Most stores offer free pickup, usually ready within a few hours.</p>
      <div className="mt-6">
        <StoreSearch selected={mine} actionLabel="Set as my store" onSelect={(s) => { localStorage.setItem("os_store", s.id); setMine(s.id); }} />
      </div>
    </div>
  );
}
