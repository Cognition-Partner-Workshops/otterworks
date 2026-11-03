"use client";

import Link from "next/link";
import { useFavorites } from "@/components/FavoritesProvider";
import { ProductCard } from "@/components/ProductCard";
import { useBag } from "@/components/BagProvider";

export default function FavoritesPage() {
  const { wishlist } = useFavorites();
  const { customer } = useBag();
  const items = wishlist?.items ?? [];
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="font-display text-3xl font-bold">Favorites</h1>
      <p className="mt-1 text-sm text-neutral-600" data-testid="favorites-note">
        {customer ? "Saved to your account, on every device." : <>Saved on this device. <Link href="/account/sign-in" className="underline">Sign in</Link> to keep them in your account.</>}
      </p>
      {items.length === 0 ? (
        <div className="mt-10 text-center" data-testid="favorites-empty">
          <p className="text-lg">Nothing saved yet.</p>
          <p className="mt-1 text-sm text-neutral-600">Tap the heart on any product to save it here.</p>
          <Link href="/c/new-arrivals" className="btn mt-4 inline-block">Shop new arrivals</Link>
        </div>
      ) : (
        <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4" data-testid="favorites-grid">
          {items.map((i) => <li key={i.productId}><ProductCard p={i.product} /></li>)}
        </ul>
      )}
    </div>
  );
}
