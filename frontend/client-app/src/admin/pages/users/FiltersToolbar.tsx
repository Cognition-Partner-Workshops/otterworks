interface FiltersToolbarProps {
  role: string;
  status: string;
  setSearch: (value: string) => void;
  setRole: (value: string) => void;
  setStatus: (value: string) => void;
}

export function FiltersToolbar({
  role,
  status,
  setSearch,
  setRole,
  setStatus,
}: FiltersToolbarProps) {
  return (
    <div className="mb-2 flex flex-wrap gap-4">
      <label className="min-w-[250px] flex-1 text-xs text-gray-500">
        Search users
        <input
          placeholder="Search by name or email"
          onKeyUp={(event) =>
            setSearch(event.currentTarget.value.trim().toLowerCase())
          }
          className="mt-1 block w-full rounded border border-gray-400 bg-transparent p-3 text-sm text-gray-800"
        />
      </label>
      <label className="text-xs text-gray-500">
        Role
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="mt-1 block w-40 rounded border border-gray-400 bg-transparent p-3 text-sm text-gray-800"
        >
          <option value="">All Roles</option>
          {["admin", "editor", "viewer"].map((value) => (
            <option key={value} value={value}>
              {value[0].toUpperCase() + value.slice(1)}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs text-gray-500">
        Status
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="mt-1 block w-40 rounded border border-gray-400 bg-transparent p-3 text-sm text-gray-800"
        >
          <option value="">All Statuses</option>
          {["active", "suspended", "pending"].map((value) => (
            <option key={value} value={value}>
              {value[0].toUpperCase() + value.slice(1)}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
