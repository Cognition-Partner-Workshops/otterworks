import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { ArrowDown, ArrowUp, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, MoreVertical, UserCircle } from 'lucide-react';
import { adminApi, getUsers, type User } from '../api';
import { Spinner } from '../layout/Shell';

type SortKey = 'displayName' | 'role' | 'status' | 'department' | 'lastLogin';
const headers: [SortKey, string][] = [['displayName', 'Name'], ['role', 'Role'], ['status', 'Status'], ['department', 'Department'], ['lastLogin', 'Last Login']];
const chipColors: Record<string, string> = { admin: 'bg-blue-50 text-blue-800', editor: 'bg-green-50 text-green-800', viewer: 'bg-purple-50 text-purple-800', active: 'bg-green-50 text-green-800', suspended: 'bg-red-50 text-red-800', pending: 'bg-orange-50 text-orange-800' };
function Chip({ value }: { value: string }) { return <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${chipColors[value] ?? ''}`}>{value}</span>; }
function shortDate(value: string) {
  return new Intl.DateTimeFormat('en-US', { year: '2-digit', month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value));
}
export default function Users() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(5);
  const [sort, setSort] = useState<{ key: SortKey; direction: 'asc' | 'desc' } | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ user: User; action: 'Suspend' | 'Delete' } | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [reloading, setReloading] = useState(false);
  const users = useQuery({ queryKey: ['admin', 'users'], queryFn: getUsers, retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: false });
  useEffect(() => { if (dialog) dialogRef.current?.showModal(); else dialogRef.current?.close(); }, [dialog]);
  const filtered = (users.data ?? []).filter(user => (!search || user.displayName.toLowerCase().includes(search) || user.email.toLowerCase().includes(search)) && (!role || user.role === role) && (!status || user.status === status));
  if (sort) filtered.sort((a, b) => {
    const left = a[sort.key] ?? ''; const right = b[sort.key] ?? '';
    return (left < right ? -1 : left > right ? 1 : 0) * (sort.direction === 'asc' ? 1 : -1);
  });
  const lastPage = Math.max(0, Math.ceil(filtered.length / size) - 1);
  const currentPage = Math.min(page, lastPage);
  useEffect(() => { if (page > lastPage) setPage(lastPage); }, [page, lastPage]);
  function changeSort(key: SortKey) {
    setSort(previous => previous?.key !== key ? { key, direction: 'asc' } : previous.direction === 'asc' ? { key, direction: 'desc' } : null);
  }
  async function mutate(user: User, action: 'Suspend' | 'Restore' | 'Delete') {
    setDialog(null); setMenu(null);
    try {
      if (action === 'Delete') await adminApi.delete(`/admin/users/${user.id}`);
      else await adminApi.put(`/admin/users/${user.id}/${action === 'Suspend' ? 'suspend' : 'activate'}`, {});
      const message = `${user.displayName} has been ${action === 'Suspend' ? 'suspended' : action === 'Restore' ? 'restored' : 'deleted'}`;
      toast(t => <span className="flex items-center gap-6">{message}<button className="font-medium text-blue-600" onClick={() => toast.dismiss(t.id)}>Dismiss</button></span>, { duration: 3000, position: 'bottom-center' });
      setReloading(true); setPage(0); setSize(5); setSort(null);
      const result = await users.refetch();
      if (result.isSuccess) setReloading(false);
    } catch { /* Angular leaves failed mutations without local feedback. */ }
  }
  return <><h1 className="mb-6 text-2xl font-semibold">User Management</h1>
    <div className="mb-6 flex flex-wrap gap-4">
      <label className="min-w-[250px] flex-1 text-xs text-gray-500">Search users<input placeholder="Search by name or email" onKeyUp={event => setSearch(event.currentTarget.value.trim().toLowerCase())} className="mt-1 block w-full rounded border border-gray-400 bg-transparent p-3 text-sm text-gray-800" /></label>
      <label className="text-xs text-gray-500">Role<select value={role} onChange={e => setRole(e.target.value)} className="mt-1 block w-40 rounded border border-gray-400 bg-transparent p-3 text-sm text-gray-800"><option value="">All Roles</option>{['admin', 'editor', 'viewer'].map(value => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
      <label className="text-xs text-gray-500">Status<select value={status} onChange={e => setStatus(e.target.value)} className="mt-1 block w-40 rounded border border-gray-400 bg-transparent p-3 text-sm text-gray-800"><option value="">All Statuses</option>{['active', 'suspended', 'pending'].map(value => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
    </div>
    {!users.data || reloading ? <Spinner /> : <div className="rounded-lg bg-white shadow">
      <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr className="border-b">{headers.map(([key, label]) => <th key={key} className="p-4 font-medium" aria-sort={sort?.key === key ? sort.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button onClick={() => changeSort(key)} className="flex items-center gap-1">{label}{sort?.key === key && (sort.direction === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />)}</button></th>)}<th className="p-4 font-medium">Actions</th></tr></thead>
        <tbody>{filtered.slice(currentPage * size, (currentPage + 1) * size).map(user => <tr key={user.id} className="cursor-pointer border-b hover:bg-gray-50" onClick={() => navigate(`/admin/users/${user.id}`)}>
          <td className="p-4"><div className="flex items-center gap-3"><UserCircle size={36} className="text-gray-400" /><div><div className="user-name font-medium">{user.displayName}</div><div className="text-xs text-gray-400">{user.email}</div></div></div></td>
          <td className="p-4"><Chip value={user.role} /></td><td className="p-4"><Chip value={user.status} /></td><td className="p-4">{user.department || '-'}</td><td className="p-4">{user.lastLogin ? shortDate(user.lastLogin) : 'Never'}</td>
          <td className="relative p-4" onClick={e => e.stopPropagation()}><button aria-label="User actions" onClick={() => setMenu(menu === user.id ? null : user.id)}><MoreVertical size={20} /></button>
            {menu === user.id && <><button aria-label="Close user actions" className="fixed inset-0 z-10 cursor-default" onClick={() => setMenu(null)} /><div role="menu" className="absolute right-4 top-10 z-20 min-w-40 rounded bg-white py-2 shadow-xl">
              <button role="menuitem" className="block w-full px-4 py-3 text-left hover:bg-gray-100" onClick={() => navigate(`/admin/users/${user.id}`)}>View Details</button>
              {user.status === 'active' && <button role="menuitem" className="block w-full px-4 py-3 text-left hover:bg-gray-100" onClick={() => { setMenu(null); setDialog({ user, action: 'Suspend' }); }}>Suspend</button>}
              {user.status === 'suspended' && <button role="menuitem" className="block w-full px-4 py-3 text-left hover:bg-gray-100" onClick={() => void mutate(user, 'Restore')}>Restore</button>}
              <button role="menuitem" className="block w-full px-4 py-3 text-left text-red-600 hover:bg-gray-100" onClick={() => { setMenu(null); setDialog({ user, action: 'Delete' }); }}>Delete</button>
            </div></>}
          </td>
        </tr>)}</tbody>
      </table></div>
      <div className="flex items-center justify-end gap-4 p-4 text-xs text-gray-600">
        <label>Items per page: <select aria-label="Items per page" value={size} onChange={event => { const next = Number(event.target.value); setPage(Math.floor(currentPage * size / next)); setSize(next); }} className="ml-2 rounded border p-2">{[5,10,25].map(value => <option key={value}>{value}</option>)}</select></label>
        <span>{filtered.length ? `${currentPage * size + 1} – ${Math.min((currentPage + 1) * size, filtered.length)} of ${filtered.length}` : '0 of 0'}</span>
        {([[ChevronFirst, 'First page', 0, currentPage === 0], [ChevronLeft, 'Previous page', currentPage - 1, currentPage === 0], [ChevronRight, 'Next page', currentPage + 1, currentPage === lastPage], [ChevronLast, 'Last page', lastPage, currentPage === lastPage]] as const).map(([Icon, label, target, disabled]) => <button key={label} aria-label={label} disabled={disabled} onClick={() => setPage(target)} className="disabled:opacity-25"><Icon size={20} /></button>)}
      </div>
    </div>}
    <dialog ref={dialogRef} onCancel={() => setDialog(null)} onClick={event => { if (event.target === event.currentTarget) setDialog(null); }} className="max-w-lg rounded bg-white p-6 shadow-xl backdrop:bg-black/40">
      {dialog && <><h2 className="mb-5 text-xl font-medium">{dialog.action} User</h2><p className="leading-relaxed text-gray-600">{dialog.action === 'Suspend' ? `Are you sure you want to suspend ${dialog.user.displayName}?` : `Are you sure you want to permanently delete ${dialog.user.displayName}? This action cannot be undone.`}</p><div className="mt-6 flex justify-end gap-4"><button onClick={() => setDialog(null)}>Cancel</button><button className="rounded bg-red-600 px-5 py-2 text-white" onClick={() => void mutate(dialog.user, dialog.action)}>{dialog.action}</button></div></>}
    </dialog>
  </>;
}
