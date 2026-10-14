import { cn } from "@/lib/utils";
import { Logo } from "@/components/ui/logo";

interface BrandLockupProps {
  className?: string;
  logoSize?: number;
}

export function BrandLockup({ className, logoSize = 32 }: BrandLockupProps) {
  return (
    <div className={cn("flex min-w-0 items-center gap-2 sm:gap-3", className)}>
      <Logo size={logoSize} />
      <div className="flex min-w-0 flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-3">
        <span className="whitespace-nowrap text-[11px] font-bold uppercase tracking-[0.16em] text-[#012169] sm:text-sm">
          BANK OF AMERICA
        </span>
        <span aria-hidden="true" className="hidden h-5 w-px bg-[#ddd] sm:block" />
        <span className="whitespace-nowrap text-xs font-normal text-[#666] sm:text-sm">
          Document Center
        </span>
      </div>
    </div>
  );
}
