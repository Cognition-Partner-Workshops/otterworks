import bofaFlag from "@/assets/bofa-flag.svg";
import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  className?: string;
}

export function Logo({ size = 32, className }: LogoProps) {
  return (
    <img
      src={bofaFlag}
      alt="Bank of America"
      width={size}
      className={cn("h-auto shrink-0 select-none", className)}
      draggable={false}
    />
  );
}
