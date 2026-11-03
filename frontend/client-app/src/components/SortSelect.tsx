"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

const OPTIONS = [
  ["featured", "Featured"], ["newest", "Newest"], ["price-asc", "Price: low to high"],
  ["price-desc", "Price: high to low"], ["rating", "Top rated"], ["discount", "Biggest discount"],
];

export function SortSelect({ value }: { value: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  return (
    <label className="flex items-center gap-2 text-sm">
      Sort by
      <select
        value={value}
        data-testid="sort"
        className="border border-neutral-300 px-2 py-1.5"
        onChange={(e) => {
          const qs = new URLSearchParams(params.toString());
          if (e.target.value === "featured") qs.delete("sort");
          else qs.set("sort", e.target.value);
          qs.delete("page");
          router.push(`${pathname}${qs.size ? `?${qs}` : ""}`, { scroll: false });
        }}
      >
        {OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}
