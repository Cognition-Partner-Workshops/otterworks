import Link from "next/link";
import type { PromotionView } from "@/lib/types";
import { Countdown } from "./Countdown";

export function PromoBanner({ promo }: { promo: PromotionView | null }) {
  if (!promo?.active || !promo.endsAt) {
    return <div className="bg-teal py-2 text-center text-sm text-white">Free standard shipping on orders $50+</div>;
  }
  return (
    <Link href="/sale" className="block bg-ink py-2 text-center text-sm text-white" data-testid="promo-banner">
      <span className="font-semibold">{promo.bannerText?.replace(/[|\s]*Ends in\s*$/i, "")}</span>
      <span className="mx-2 opacity-50">|</span>
      <Countdown endsAt={promo.endsAt} className="font-mono" />
    </Link>
  );
}
