import { COMPANY } from "@/lib/corporate";

export function ConceptBanner() {
  return (
    <div className="flex h-6 items-center justify-center bg-otter-900 px-2 text-center text-[11px] text-white/80">
      {COMPANY.disclaimer}
    </div>
  );
}
