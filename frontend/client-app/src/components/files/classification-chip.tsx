import { classifyFile } from "@/lib/classification";

export function ClassificationChip({ fileName, className = "" }: Readonly<{ fileName: string; className?: string }>) {
  const { label, chipClassName } = classifyFile(fileName);
  return (
    <span
      title={`Data classification: ${label}`}
      className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wide leading-none flex-shrink-0 ${chipClassName} ${className}`}
    >
      {label}
    </span>
  );
}
