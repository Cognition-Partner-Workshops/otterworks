import { classifyFileName } from "@/lib/classification";

interface ClassificationChipProps {
  fileName: string;
  className?: string;
}

export function ClassificationChip({ fileName, className = "" }: Readonly<ClassificationChipProps>) {
  const { label, chipClassName } = classifyFileName(fileName);
  return (
    <span
      title={`Data classification: ${label}`}
      className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wide leading-none ${chipClassName} ${className}`}
    >
      {label}
    </span>
  );
}
