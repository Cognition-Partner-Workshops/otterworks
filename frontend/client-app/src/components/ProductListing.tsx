import Link from "next/link";
import { api } from "@/lib/api";
import { sortSizes, titleCase } from "@/lib/format";
import { ProductCard } from "./ProductCard";
import { SortSelect } from "./SortSelect";

export type Search = Record<string, string | string[] | undefined>;

const PRICES = [
  { key: "0-25", label: "Under $25" },
  { key: "25-50", label: "$25 - $50" },
  { key: "50-100", label: "$50 - $100" },
  { key: "100-", label: "$100 and up" },
];
const FILTER_KEYS = ["category", "size", "color", "fit", "price", "department"] as const;
const PAGE_SIZE = 24;

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function values(sp: Search, key: string): string[] {
  return (one(sp[key]) ?? "").split(",").filter(Boolean);
}

function hrefWith(base: string, sp: Search, key: string, value: string | null, multi = true): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    const s = one(v);
    if (s && k !== "page") qs.set(k, s);
  }
  if (value === null) qs.delete(key);
  else if (multi) {
    const cur = values(sp, key);
    const next = cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value];
    if (next.length) qs.set(key, next.join(","));
    else qs.delete(key);
  } else qs.set(key, value);
  const s = qs.toString();
  return s ? `${base}?${s}` : base;
}

export async function ProductListing(props: {
  base: string; title: string; description?: string; sp: Search;
  scope: { department?: string; collection?: string; onSale?: boolean; q?: string };
}) {
  const { base, title, description, sp, scope } = props;
  const price = one(sp.price);
  const [lo, hi] = price ? price.split("-") : [];
  const page = Math.max(1, parseInt(one(sp.page) ?? "1", 10) || 1);
  const data = await api.products({
    department: scope.department ?? one(sp.department),
    collection: scope.collection,
    onSale: scope.onSale ? "true" : undefined,
    q: scope.q,
    category: one(sp.category),
    size: one(sp.size),
    color: one(sp.color),
    fit: one(sp.fit),
    priceMin: lo ? String(parseInt(lo, 10) * 100) : undefined,
    priceMax: hi ? String(parseInt(hi, 10) * 100 - 1) : undefined,
    sort: one(sp.sort),
    page: "1",
    pageSize: String(page * PAGE_SIZE),
  });
  const active = FILTER_KEYS.flatMap((k) => values(sp, k).map((v) => ({ k, v })));
  const f = data.facets;
  const group = (key: string, label: string, facets: { value: string; count: number }[], render?: (v: string) => React.ReactNode) =>
    facets.length > 0 && (
      <details open className="border-b border-neutral-200 py-3">
        <summary className="cursor-pointer text-sm font-semibold">{label}</summary>
        <ul className={`mt-3 ${key === "size" ? "grid grid-cols-4 gap-1" : "space-y-1.5"}`}>
          {facets.map((x) => {
            const on = values(sp, key).includes(x.value.toLowerCase());
            return (
              <li key={x.value}>
                <Link
                  href={hrefWith(base, sp, key, x.value.toLowerCase())}
                  scroll={false}
                  data-testid={`filter-${key}-${x.value.toLowerCase()}`}
                  aria-pressed={on}
                  className={key === "size"
                    ? `block border py-1 text-center text-xs ${on ? "border-teal bg-teal text-white" : "border-neutral-300 hover:border-ink"}`
                    : `flex items-center gap-2 text-sm ${on ? "font-semibold text-teal" : "hover:underline"}`}
                >
                  {key !== "size" && <span className={`inline-block h-3.5 w-3.5 border ${on ? "border-teal bg-teal" : "border-neutral-400"}`} />}
                  {render ? render(x.value) : x.value}
                  {key !== "size" && <span className="text-neutral-400">({x.count})</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </details>
    );

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <nav className="mb-2 text-xs text-neutral-500" aria-label="Breadcrumb">
        <Link href="/" className="hover:underline">Home</Link> / <span>{title}</span>
      </nav>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold" data-testid="plp-title">{title}</h1>
          {description && <p className="mt-1 text-sm text-neutral-600">{description}</p>}
          <p className="mt-1 text-sm text-neutral-500" data-testid="result-count">{data.total} items</p>
        </div>
        <SortSelect value={one(sp.sort) ?? "featured"} />
      </div>
      {active.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
          {active.map(({ k, v }) => (
            <Link key={k + v} href={hrefWith(base, sp, k, k === "price" ? null : v, k !== "price")} scroll={false} className="rounded-full border border-neutral-300 px-3 py-1 hover:border-ink">
              {titleCase(k === "price" ? PRICES.find((p) => p.key === v)?.label ?? v : v)} ×
            </Link>
          ))}
          <Link href={base} className="underline">Clear all</Link>
        </div>
      )}
      <div className="grid gap-8 md:grid-cols-[220px_1fr]">
        <aside aria-label="Filters">
          {group("category", "Category", f.categories)}
          {group("size", "Size", sortSizes(f.sizes))}
          {group("color", "Color", f.colors, (v) => titleCase(v))}
          {group("fit", "Fit", f.fits)}
          <details open className="border-b border-neutral-200 py-3">
            <summary className="cursor-pointer text-sm font-semibold">Price</summary>
            <ul className="mt-3 space-y-1.5">
              {PRICES.map((p) => (
                <li key={p.key}>
                  <Link href={hrefWith(base, sp, "price", price === p.key ? null : p.key, false)} scroll={false} className={`text-sm ${price === p.key ? "font-semibold text-teal" : "hover:underline"}`}>
                    {p.label}
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        </aside>
        <section>
          {data.items.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-lg font-semibold">No matches</p>
              <p className="mt-2 text-sm text-neutral-600">Try removing a filter, or browse <Link href="/c/new-arrivals" className="underline">New Arrivals</Link>.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-x-4 gap-y-8 lg:grid-cols-4" data-testid="product-grid">
              {data.items.map((p) => <ProductCard key={p.id} p={p} />)}
            </div>
          )}
          {data.items.length < data.total && (
            <div className="mt-10 text-center">
              <p className="mb-3 text-sm text-neutral-500">Showing {data.items.length} of {data.total}</p>
              <Link href={hrefWith(base, { ...sp }, "page", String(page + 1), false)} scroll={false} className="btn-outline">Load more</Link>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
