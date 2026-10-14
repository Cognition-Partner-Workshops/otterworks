import { COMPANY } from "@/lib/corporate";

export function ConceptBanner() {
  return (
    <div className="flex min-h-6 items-center justify-center border-b border-[#ddd] bg-[#f5f5f5] px-2 py-0.5 text-center text-[12px] italic leading-tight text-[#333]">
      {COMPANY.disclaimer}
    </div>
  );
}
