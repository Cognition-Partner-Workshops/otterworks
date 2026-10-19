import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AppRoutes } from "@/AppRoutes";
import { fixtures as baseFixtures } from "@/fixtures/fixtures";
import type { Fixtures, Person } from "@/fixtures/types";
import { WorkbenchProvider, type WorkbenchUser } from "@/WorkbenchContext";
import { isValidTenantId } from "@/tenant";
import { RemoteStorage, setWorkbenchStorage, STORAGE_DOCS } from "@/stores/workbenchStorage";
import "./globals.css";

interface StateResponse {
  boards: unknown | null;
  chat: unknown | null;
  settings: Record<string, unknown> | null;
}

function personForUser(user: WorkbenchUser): Person {
  const sanitizedSub = Array.from(user.sub).map((character) => (
    /^[a-zA-Z0-9_-]$/.test(character) ? character : `_${character.codePointAt(0)!.toString(16)}_`
  )).join("");
  const id = `user-${sanitizedSub || "attendee"}`;
  const initials = user.name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "U";
  return { id, name: user.name, initials, title: user.email, kind: "human" };
}

function readSettings(storage: Storage): Record<string, unknown> {
  try {
    const value = storage.getItem(STORAGE_DOCS["workbench.settings.v1"]);
    if (!value) return {};
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function persistSettings(storage: Storage, tenantId: string): void {
  storage.setItem(STORAGE_DOCS["workbench.settings.v1"], JSON.stringify({ ...readSettings(storage), tenantId }));
}

function renderWorkbench(fixtures: Fixtures, user: WorkbenchUser, mode: "hosted" | "static", tenantId: string, storage: Storage) {
  const root = createRoot(document.getElementById("root")!);
  const updateTenant = (value: string) => {
    const tenant = value && isValidTenantId(value) ? value : "";
    persistSettings(storage, tenant);
  };
  root.render(
    <StrictMode>
      <WorkbenchProvider value={{ fixtures, user, mode, tenantId, setTenantId: updateTenant }}>
        <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <AppRoutes />
        </BrowserRouter>
      </WorkbenchProvider>
    </StrictMode>,
  );
}

async function startWorkbench(): Promise<void> {
  const mode = import.meta.env.VITE_WORKBENCH_MODE === "hosted" ? "hosted" : "static";
  let storage: Storage = window.localStorage;
  let fixtures = baseFixtures;
  let user: WorkbenchUser = {
    sub: "dwhitfield",
    name: baseFixtures.people.find((person) => person.id === "dwhitfield")?.name ?? "Local user",
    email: baseFixtures.people.find((person) => person.id === "dwhitfield")?.title ?? "",
  };
  let stateSettings: Record<string, unknown> = readSettings(storage);

  if (mode === "hosted") {
    const meResponse = await fetch("/api/me", { credentials: "same-origin" });
    if (meResponse.status === 401) {
      const returnTo = `${window.location.pathname}${window.location.search}`;
      window.location.assign(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
      return;
    }
    if (!meResponse.ok) throw new Error(`Could not load identity: ${meResponse.status}`);
    user = await meResponse.json() as WorkbenchUser;
    const stateResponse = await fetch("/api/state", { credentials: "same-origin" });
    if (!stateResponse.ok) throw new Error(`Could not load saved state: ${stateResponse.status}`);
    const state = await stateResponse.json() as StateResponse;
    const remoteStorage = new RemoteStorage();
    await remoteStorage.hydrate(state as unknown as Record<string, unknown>);
    storage = remoteStorage;
    setWorkbenchStorage(remoteStorage);
    stateSettings = state.settings ?? {};
    const person = personForUser(user);
    fixtures = {
      ...baseFixtures,
      currentUserId: person.id,
      people: [...baseFixtures.people.filter((candidate) => candidate.id !== person.id), person],
    };
  } else {
    setWorkbenchStorage(window.localStorage);
  }

  const url = new URL(window.location.href);
  const requestedTenant = url.searchParams.get("tenant");
  const savedTenant = typeof stateSettings.tenantId === "string" && isValidTenantId(stateSettings.tenantId)
    ? stateSettings.tenantId
    : "";
  const tenantId = requestedTenant && isValidTenantId(requestedTenant) ? requestedTenant : savedTenant;
  if (requestedTenant !== null) {
    if (requestedTenant && isValidTenantId(requestedTenant)) persistSettings(storage, tenantId);
    url.searchParams.delete("tenant");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }
  renderWorkbench(fixtures, user, mode, tenantId, storage);
}

void startWorkbench().catch((error: unknown) => {
  console.error(error);
  document.getElementById("root")!.textContent = "Workbench could not be loaded.";
});
