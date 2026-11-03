import { money } from "@/lib/format";
import type { Price as PriceInfo } from "@/lib/types";

export function Price({ price, size = "sm" }: { price: PriceInfo; size?: "sm" | "lg" }) {
  const big = size === "lg" ? "text-2xl" : "text-sm";
  if (!price.onSale) return <span className={`${big} font-semibold`} data-testid="price">{money(price.priceCents)}</span>;
  return (
    <span className="inline-flex flex-wrap items-baseline gap-2" data-testid="price">
      <span className={`${big} font-semibold text-sale`}>{money(price.priceCents)}</span>
      <s className="text-xs text-neutral-500" aria-label={`Was ${money(price.listCents)}`}>{money(price.listCents)}</s>
      {price.percentOff > 0 && <span className="text-xs font-semibold text-sale">{price.percentOff}% off</span>}
    </span>
  );
}
