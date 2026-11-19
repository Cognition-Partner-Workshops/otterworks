import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { adminApi, getUsers, type User } from "../api";
import { Spinner } from "../layout/Spinner";
import { FiltersToolbar } from "./users/FiltersToolbar";
import { UsersTable, type SortKey } from "./users/UsersTable";
import { Paginator } from "./users/Paginator";
import { UserConfirmDialog } from "./users/UserConfirmDialog";

export default function Users() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(5);
  const [sort, setSort] = useState<{
    key: SortKey;
    direction: "asc" | "desc";
  } | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{
    user: User;
    action: "Suspend" | "Delete";
  } | null>(null);
  const [reloading, setReloading] = useState(false);
  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: getUsers,
    retry: false,
    gcTime: 0,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
  });
  const filtered = (users.data ?? []).filter(
    (user) =>
      (!search ||
        user.displayName.toLowerCase().includes(search) ||
        user.email.toLowerCase().includes(search)) &&
      (!role || user.role === role) &&
      (!status || user.status === status)
  );
  if (sort) {
    filtered.sort((a, b) => {
      const left = a[sort.key] ?? "";
      const right = b[sort.key] ?? "";
      return (
        (left < right ? -1 : left > right ? 1 : 0) *
        (sort.direction === "asc" ? 1 : -1)
      );
    });
  }
  const lastPage = Math.max(0, Math.ceil(filtered.length / size) - 1);
  const currentPage = Math.min(page, lastPage);

  useEffect(() => {
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [page, lastPage]);

  function changeSort(key: SortKey) {
    setSort((previous) =>
      previous?.key !== key
        ? { key, direction: "asc" }
        : previous.direction === "asc"
          ? { key, direction: "desc" }
          : null
    );
  }

  async function mutate(user: User, action: "Suspend" | "Restore" | "Delete") {
    setDialog(null);
    setMenu(null);
    try {
      if (action === "Delete") {
        await adminApi.delete(`/admin/users/${user.id}`);
      } else {
        await adminApi.put(
          `/admin/users/${user.id}/${action === "Suspend" ? "suspend" : "activate"}`,
          {}
        );
      }
      const message = `${user.displayName} has been ${action === "Suspend" ? "suspended" : action === "Restore" ? "restored" : "deleted"}`;
      toast(
        (t) => (
          <span className="flex items-center gap-6">
            {message}
            <button
              className="font-medium text-blue-600"
              onClick={() => toast.dismiss(t.id)}
            >
              Dismiss
            </button>
          </span>
        ),
        { duration: 3000, position: "bottom-center" }
      );
      setReloading(true);
      setPage(0);
      setSize(5);
      setSort(null);
      const result = await users.refetch();
      if (result.isSuccess) {
        setReloading(false);
      }
    } catch {
      /* Angular leaves failed mutations without local feedback. */
    }
  }

  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold">User Management</h1>
      <FiltersToolbar
        role={role}
        status={status}
        setSearch={setSearch}
        setRole={setRole}
        setStatus={setStatus}
      />
      {!users.data || reloading ? (
        <Spinner />
      ) : (
        <div className="rounded-lg bg-white shadow">
          <UsersTable
            users={filtered.slice(currentPage * size, (currentPage + 1) * size)}
            sort={sort}
            menu={menu}
            changeSort={changeSort}
            setMenu={setMenu}
            onView={(user) => navigate(`/admin/users/${user.id}`)}
            onAction={(user, action) => {
              if (action === "Restore") {
                void mutate(user, action);
              } else {
                setDialog({ user, action });
              }
            }}
          />
          <Paginator
            currentPage={currentPage}
            size={size}
            total={filtered.length}
            setPage={setPage}
            setSize={setSize}
          />
        </div>
      )}
      <UserConfirmDialog
        dialog={dialog}
        onCancel={() => setDialog(null)}
        onConfirm={(user, action) => void mutate(user, action)}
      />
    </>
  );
}
