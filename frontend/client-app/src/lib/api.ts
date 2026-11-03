import "server-only";
import type { Collection, ProductDetail, ProductPage, PromotionView } from "./types";

const BASE = process.env.ORDER_SERVICE_URL ?? "http://localhost:8080";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string, revalidate = 30): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, { next: { revalidate } });
  if (!res.ok) throw new ApiError(res.status, `GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  promotion: () => get<PromotionView>("/promotions/active", 60).catch(() => null),
  collections: () => get<Collection[]>("/collections", 300),
  products: (params: Record<string, string | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
    return get<ProductPage>(`/products?${qs}`, 15);
  },
  product: (id: string) => get<ProductDetail>(`/products/${encodeURIComponent(id)}`, 5),
};
