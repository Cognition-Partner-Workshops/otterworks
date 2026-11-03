import { ProductListing, type Search } from "@/components/ProductListing";

export const dynamic = "force-dynamic";
export const metadata = { title: "Search" };

export default async function SearchPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const q = (Array.isArray(sp.q) ? sp.q[0] : sp.q) ?? "";
  return <ProductListing base="/search" title={q ? `Results for "${q}"` : "Search"} sp={sp} scope={{ q }} />;
}
