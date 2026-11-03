"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { Bag, Customer } from "@/lib/types";

const KEY = "os_bag";

interface BagContextValue {
  bag: Bag | null;
  customer: Customer | null;
  ready: boolean;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  add: (sku: string, quantity: number) => Promise<void>;
  setQuantity: (sku: string, quantity: number) => Promise<void>;
  remove: (sku: string) => Promise<void>;
  applyPromo: (code: string) => Promise<void>;
  removePromo: () => Promise<void>;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  register: (body: { email: string; password: string; firstName: string; lastName: string }) => Promise<void>;
  signOut: () => Promise<void>;
  reset: () => void;
}

const BagContext = createContext<BagContextValue | null>(null);

export function useBag(): BagContextValue {
  const ctx = useContext(BagContext);
  if (!ctx) throw new Error("useBag must be used inside BagProvider");
  return ctx;
}

export function BagProvider({ children }: { children: React.ReactNode }) {
  const [bag, setBag] = useState<Bag | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [ready, setReady] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const store = useCallback((b: Bag | null) => {
    setBag(b);
    if (b) localStorage.setItem(KEY, b.id);
    else localStorage.removeItem(KEY);
  }, []);

  const load = useCallback(async () => {
    let memberBag: string | null = null;
    try {
      const me = await call<{ customer: Customer; bagId: string | null }>("/auth/me");
      setCustomer(me.customer);
      memberBag = me.bagId;
    } catch {
      setCustomer(null);
    }
    const id = memberBag ?? localStorage.getItem(KEY);
    if (id) {
      try {
        store(await call<Bag>(`/bags/${id}`));
      } catch {
        store(null);
      }
    }
    setReady(true);
  }, [store]);

  useEffect(() => {
    void load();
  }, [load]);

  const ensureBag = useCallback(async (): Promise<string> => {
    if (bag) return bag.id;
    const created = await call<Bag>("/bags", { method: "POST" });
    store(created);
    return created.id;
  }, [bag, store]);

  const add = useCallback(async (sku: string, quantity: number) => {
    const id = await ensureBag();
    try {
      store(await call<Bag>(`/bags/${id}/items`, { method: "POST", body: { sku, quantity } }));
    } catch (e) {
      if (e instanceof HttpError && e.status === 404) {
        const created = await call<Bag>("/bags", { method: "POST" });
        store(await call<Bag>(`/bags/${created.id}/items`, { method: "POST", body: { sku, quantity } }));
      } else throw e;
    }
    setDrawerOpen(true);
  }, [ensureBag, store]);

  const mutate = useCallback(async (path: string, method: string, body?: unknown) => {
    if (!bag) return;
    store(await call<Bag>(`/bags/${bag.id}${path}`, { method, body }));
  }, [bag, store]);

  const signedIn = useCallback(async (res: { customer: Customer; bagId: string | null }) => {
    setCustomer(res.customer);
    if (res.bagId) store(await call<Bag>(`/bags/${res.bagId}`));
  }, [store]);

  const value = useMemo<BagContextValue>(() => ({
    bag, customer, ready, drawerOpen, setDrawerOpen, add,
    setQuantity: (sku, q) => mutate(`/items/${encodeURIComponent(sku)}`, "PATCH", { quantity: q }),
    remove: (sku) => mutate(`/items/${encodeURIComponent(sku)}`, "DELETE"),
    applyPromo: (code) => mutate("/promo", "POST", { code }),
    removePromo: () => mutate("/promo", "DELETE"),
    refresh: load,
    signIn: async (email, password) => signedIn(await call("/auth/login", { method: "POST", body: { email, password, bagId: bag?.id } })),
    register: async (body) => signedIn(await call("/auth/register", { method: "POST", body: { ...body, bagId: bag?.id } })),
    signOut: async () => {
      await call("/auth/logout", { method: "POST" });
      setCustomer(null);
      store(null);
    },
    reset: () => store(null),
  }), [bag, customer, ready, drawerOpen, add, mutate, load, signedIn, store]);

  return <BagContext.Provider value={value}>{children}</BagContext.Provider>;
}
