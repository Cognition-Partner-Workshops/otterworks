import Link from "next/link";
import { notFound } from "next/navigation";
import { PdpBuy } from "@/components/PdpBuy";
import { ProductCard } from "@/components/ProductCard";
import { RecentlyViewed } from "@/components/RecentlyViewed";
import { Reviews } from "@/components/Reviews";
import { api, ApiError } from "@/lib/api";
import { titleCase } from "@/lib/format";

export const dynamic = "force-dynamic";

async function load(id: string) {
  try {
    return await api.product(id);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const p = await load((await params).id);
  return { title: p.name, description: p.description };
}

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const p = await load((await params).id);
  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <nav className="mb-4 text-xs text-neutral-500" aria-label="Breadcrumb">
        <Link href="/" className="hover:underline">Home</Link> /{" "}
        <Link href={`/c/${p.department}`} className="hover:underline">{titleCase(p.department)}</Link> /{" "}
        <Link href={`/c/${p.department}?category=${encodeURIComponent(p.category.toLowerCase())}`} className="hover:underline">{p.category}</Link>
      </nav>
      <PdpBuy p={p} />
      {p.related.length > 0 && (
        <section className="mt-16" data-testid="complete-the-look">
          <h2 className="mb-4 font-display text-2xl font-bold">Complete the look</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{p.related.map((r) => <ProductCard key={r.id} p={r} />)}</div>
        </section>
      )}
      <Reviews productId={p.id} sizes={[...new Set(p.skus.map((s) => s.size))]} />
      {p.recommended.length > 0 && (
        <section className="mt-16" data-testid="recommended">
          <h2 className="mb-4 font-display text-2xl font-bold">You may also like</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{p.recommended.slice(0, 4).map((r) => <ProductCard key={r.id} p={r} />)}</div>
        </section>
      )}
      <RecentlyViewed current={p} />
    </div>
  );
}
