import { money } from "@/lib/format";
import type { Bag } from "@/lib/types";

export function FreeShippingBar({ bag }: { bag: Bag }) {
  const threshold = bag.freeShippingThresholdCents;
  const pct = Math.min(100, Math.round(((threshold - bag.freeShippingRemainingCents) / threshold) * 100));
  const done = bag.freeShippingRemainingCents === 0;
  return (
    <div data-testid="free-shipping">
      <p className={`text-sm ${done ? "font-semibold text-teal" : ""}`}>
        {done ? "You've unlocked free standard shipping." : <>You&apos;re <strong>{money(bag.freeShippingRemainingCents)}</strong> away from free standard shipping.</>}
      </p>
      <div className="mt-2 h-2 rounded-full bg-neutral-200" role="progressbar" aria-label="Progress to free shipping" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <div className="h-2 rounded-full bg-teal transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
