import { COMPANY } from "@/lib/corporate";

export function ConceptBanner() {
  return (
    <div className="flex min-h-6 items-center justify-center bg-otter-900 px-2 py-0.5 text-center text-[11px] leading-tight text-white/80">
      {COMPANY.disclaimer}
    </div>
  );
}
