import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import type { User } from "@/types";

export const API = "http://localhost:3000/api/v1";

export const testUser: User = {
  id: "user-1",
  email: "otter@otterworks.test",
  displayName: "Olive Otter",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

export function resetStores(user: User | null = testUser) {
  useAuthStore.setState({ user, isAuthenticated: !!user, isLoading: false });
  useUIStore.setState({
    sidebarOpen: true,
    viewMode: "grid",
    sortConfig: { field: "updatedAt", direction: "desc" },
  });
}

export function renderAt(
  ui: ReactElement,
  { path = "/", route = "*" }: { path?: string; route?: string } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={ui} />
          <Route path="*" element={<div data-testid="other-route" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

export function isoDaysAgo(days: number, hours = 0): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(d.getHours() - hours);
  return d.toISOString();
}

export function rawFile(id: string, name: string, updatedAt: string, sizeBytes = 1024) {
  return {
    id,
    name,
    mime_type: "text/plain",
    size_bytes: sizeBytes,
    folder_id: null,
    owner_id: testUser.id,
    is_trashed: false,
    created_at: updatedAt,
    updated_at: updatedAt,
  };
}

export function rawDocument(id: string, title: string, updatedAt: string) {
  return {
    id,
    title,
    content: "",
    owner_id: testUser.id,
    owner_name: testUser.displayName,
    parent_id: null,
    shared_with: [],
    collaborators: [],
    tags: [],
    word_count: 0,
    created_at: updatedAt,
    updated_at: updatedAt,
  };
}
