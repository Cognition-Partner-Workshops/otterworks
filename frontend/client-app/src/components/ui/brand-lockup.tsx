import { cn } from "@/lib/utils";
import bofaLogo from "@/assets/bofa-logo.svg";

interface BrandLockupProps {
  className?: string;
}

export function BrandLockup({ className }: BrandLockupProps) {
  return (
    <div className={cn("flex min-w-0 items-center gap-2 sm:gap-3", className)}>
      <img
        src={bofaLogo}
        alt="Bank of America"
        className="h-[18px] w-auto shrink-0 select-none sm:h-6"
        draggable={false}
      />
      <span aria-hidden="true" className="h-5 w-px shrink-0 bg-[#ddd]" />
      <span className="whitespace-nowrap text-xs font-normal text-[#666] sm:text-sm">
        Document Center
      </span>
    </div>
  );
}
