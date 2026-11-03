"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { Wishlist } from "@/lib/types";
import { useBag } from "./BagProvider";

const KEY = "os_wishlist";

interface FavoritesValue {
  wishlist: Wishlist | null;
  has: (productId: string) => boolean;
  toggle: (productId: string, color?: string | null) => Promise<boolean>;
  refresh: () => Promise<void>;
}

const FavoritesContext = createContext<FavoritesValue | null>(null);

export function useFavorites(): FavoritesValue {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error("useFavorites must be used inside FavoritesProvider");
  return ctx;
}

/** Guest favorites live under an id in localStorage; signing in claims them into the member's list. */
export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const { customer, ready } = useBag();
  const [wishlist, setWishlist] = useState<Wishlist | null>(null);

  const keep = useCallback((w: Wishlist | null) => {
    setWishlist(w);
    if (w && !w.member) localStorage.setItem(KEY, w.id);
    else localStorage.removeItem(KEY);
  }, []);

  const refresh = useCallback(async () => {
    const guestId = localStorage.getItem(KEY);
    try {
      if (customer) {
        keep(await call<Wishlist>("/wishlists/claim", { method: "POST", body: { wishlistId: guestId } }));
      } else if (guestId) {
        keep(await call<Wishlist>(`/wishlists/${guestId}`));
      } else {
        setWishlist(null);
      }
    } catch (e) {
      if (e instanceof HttpError && e.status === 404) keep(null);
    }
  }, [customer, keep]);

  useEffect(() => {
    if (ready) void refresh();
  }, [ready, refresh]);

  const ensure = useCallback(async (): Promise<string> => {
    if (wishlist) return wishlist.id;
    const created = await call<Wishlist>("/wishlists", { method: "POST" });
    keep(created);
    return created.id;
  }, [wishlist, keep]);

  const value = useMemo<FavoritesValue>(() => ({
    wishlist,
    has: (id) => !!wishlist?.items.some((i) => i.productId === id),
    toggle: async (productId, color) => {
      const id = await ensure();
      const saved = wishlist?.items.some((i) => i.productId === productId);
      const next = await call<Wishlist>(`/wishlists/${id}/items/${encodeURIComponent(productId)}`,
        saved ? { method: "DELETE" } : { method: "PUT", body: { color: color ?? null } });
      keep(next);
      return !saved;
    },
    refresh,
  }), [wishlist, ensure, keep, refresh]);

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function FavoriteButton({ productId, color, name, className = "" }: { productId: string; color?: string | null; name: string; className?: string }) {
  const { has, toggle } = useFavorites();
  const [busy, setBusy] = useState(false);
  const on = has(productId);
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={on ? `Remove ${name} from favorites` : `Save ${name} to favorites`}
      disabled={busy}
      onClick={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setBusy(true);
        try { await toggle(productId, color); } finally { setBusy(false); }
      }}
      className={`flex h-9 w-9 items-center justify-center rounded-full bg-white/90 shadow hover:bg-white ${className}`}
      data-testid="favorite-button"
    >
      <svg viewBox="0 0 24 24" className={`h-5 w-5 ${on ? "fill-sale stroke-sale" : "fill-none stroke-ink"}`} strokeWidth="2" aria-hidden="true">
        <path d="M12 21s-7.5-4.6-9.5-9.1C1.1 8.6 3.2 5 6.7 5c2 0 3.4 1.1 4.3 2.4h2C13.9 6.1 15.3 5 17.3 5c3.5 0 5.6 3.6 4.2 6.9C19.5 16.4 12 21 12 21z" />
      </svg>
    </button>
  );
}
