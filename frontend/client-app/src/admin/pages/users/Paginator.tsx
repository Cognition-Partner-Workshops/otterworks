import {
  ChevronFirst,
  ChevronLast,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface PaginatorProps {
  currentPage: number;
  size: number;
  total: number;
  setPage: (page: number) => void;
  setSize: (size: number) => void;
}

export function Paginator({
  currentPage,
  size,
  total,
  setPage,
  setSize,
}: PaginatorProps) {
  const lastPage = Math.max(0, Math.ceil(total / size) - 1);
  return (
    <div className="flex items-center justify-end gap-4 p-4 text-xs text-gray-600">
      <label>
        Items per page:{" "}
        <select
          aria-label="Items per page"
          value={size}
          onChange={(event) => {
            const next = Number(event.target.value);
            setPage(Math.floor((currentPage * size) / next));
            setSize(next);
          }}
          className="ml-2 rounded border p-2"
        >
          {[5, 10, 25].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <span>
        {total
          ? `${currentPage * size + 1} – ${Math.min((currentPage + 1) * size, total)} of ${total}`
          : "0 of 0"}
      </span>
      {(
        [
          [ChevronFirst, "First page", 0, currentPage === 0],
          [ChevronLeft, "Previous page", currentPage - 1, currentPage === 0],
          [
            ChevronRight,
            "Next page",
            currentPage + 1,
            currentPage === lastPage,
          ],
          [ChevronLast, "Last page", lastPage, currentPage === lastPage],
        ] as const
      ).map(([Icon, label, target, disabled]) => (
        <button
          key={label}
          aria-label={label}
          disabled={disabled}
          onClick={() => setPage(target)}
          className="disabled:opacity-25"
        >
          <Icon size={20} />
        </button>
      ))}
    </div>
  );
}
