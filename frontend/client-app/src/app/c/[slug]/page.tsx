import { notFound } from "next/navigation";
import { ProductListing, type Search } from "@/components/ProductListing";
import { DEPARTMENT_SLUGS } from "@/config/site";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const c = (await api.collections()).find((x) => x.slug === slug);
  return { title: c?.name ?? "Shop" };
}

export default async function CollectionPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<Search> }) {
  const [{ slug }, sp] = await Promise.all([params, searchParams]);
  const c = (await api.collections()).find((x) => x.slug === slug);
  if (!c) notFound();
  const isDept = DEPARTMENT_SLUGS.includes(slug);
  return (
    <ProductListing
      base={`/c/${slug}`}
      title={c.name}
      description={c.description}
      sp={sp}
      scope={isDept ? { department: slug } : { collection: slug }}
    />
  );
}
