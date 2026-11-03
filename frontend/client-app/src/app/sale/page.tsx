import { ProductListing, type Search } from "@/components/ProductListing";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "Sale" };

export default async function SalePage({ searchParams }: { searchParams: Promise<Search> }) {
  const [sp, promo] = await Promise.all([searchParams, api.promotion()]);
  const description = promo?.active
    ? `${promo.headline}. Excludes ${promo.excludedCollections.map((c) => c.replace(/-/g, " ")).join(" and ")}.`
    : "Markdowns across the store. Prices as marked.";
  return <ProductListing base="/sale" title={promo?.active ? promo.name ?? "Sale" : "Sale"} description={description} sp={sp} scope={{ onSale: true }} />;
}
