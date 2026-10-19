import brindlemoorSeal from "@/assets/brindlemoor-seal.svg";
import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  className?: string;
}

export function Logo({ size = 32, className }: LogoProps) {
  return (
    <img
      src={brindlemoorSeal}
      alt="Brindlemoor DRS logo"
      width={size}
      height={size}
      className={cn("shrink-0 select-none", className)}
      draggable={false}
    />
  );
}
