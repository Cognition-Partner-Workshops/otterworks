"use client";

import { useEffect, useState } from "react";
import type { ProductCard as Card, ProductDetail } from "@/lib/types";
import { ProductCard } from "./ProductCard";

const KEY = "os_recent";
const MAX = 12;

function toCard(p: ProductDetail): Card {
  const { images, skus, related, recommended, description, details, materials, ...rest } = p;
  void skus; void related; void recommended; void description; void details; void materials;
  return { ...rest, image: images[0]?.url ?? null, hoverImage: images[1]?.url ?? null };
}

/** Records this product and shows the others the shopper viewed on this device. */
export function RecentlyViewed({ current }: { current: ProductDetail }) {
  const [items, setItems] = useState<Card[]>([]);
  useEffect(() => {
    let list: Card[] = [];
    try { list = JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { list = []; }
    const others = list.filter((c) => c.id !== current.id);
    localStorage.setItem(KEY, JSON.stringify([toCard(current), ...others].slice(0, MAX)));
    setItems(others.slice(0, 4));
  }, [current]);
  if (items.length === 0) return null;
  return (
    <section className="mt-16" data-testid="recently-viewed">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="font-display text-2xl font-bold">Recently viewed</h2>
        <button type="button" className="text-sm underline" onClick={() => { localStorage.setItem(KEY, JSON.stringify([toCard(current)])); setItems([]); }}>Clear</button>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{items.map((c) => <ProductCard key={c.id} p={c} />)}</div>
    </section>
  );
}
