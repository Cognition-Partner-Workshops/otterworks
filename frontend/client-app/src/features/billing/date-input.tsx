import { useEffect, useRef } from "react";

export function isCompleteDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function BillingDateInput({ id, value, onChange, describedBy }: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  describedBy?: string;
}) {
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (input.current) input.current.value = value;
  }, [value]);

  return <input
    ref={input}
    id={id}
    type="date"
    defaultValue={value}
    onChange={(event) => {
      const next = event.currentTarget.value;
      if (event.currentTarget.validity.valid && isCompleteDate(next)) onChange(next);
    }}
    aria-describedby={describedBy}
    className="w-full rounded-lg border border-gray-300 px-3 py-2"
  />;
}
