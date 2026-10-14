import { COMPANY } from "@/lib/corporate";

export function ConceptBanner() {
  return (
    <div role="note"
      className="flex min-h-10 items-center justify-center bg-[#E31837] px-4 py-2 text-center text-[15px] font-semibold leading-snug text-white">
      {COMPANY.disclaimer}
    </div>
  );
}
