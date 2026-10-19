export const STORAGE_DOCS = {
  "workbench.boards.v1": "boards",
  "workbench.chat.v1": "chat",
  "workbench.settings.v1": "settings",
} as const;

export type WorkbenchStorageKey = keyof typeof STORAGE_DOCS;

export class RemoteStorage implements Storage {
  private readonly values = new Map<string, string>();
  private resetStarted = false;
  private pendingWrites: Promise<void> = Promise.resolve();

  async hydrate(state: Record<string, unknown>): Promise<void> {
    for (const key of Object.keys(STORAGE_DOCS) as WorkbenchStorageKey[]) {
      const doc = STORAGE_DOCS[key];
      const value = state[doc];
      if (value !== null && value !== undefined) this.values.set(key, JSON.stringify(value));
    }
  }

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
    void this.resetRemote();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return [...this.values.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
    if (key in STORAGE_DOCS) void this.resetRemote();
  }

  setItem(key: string, value: string): void {
    this.values.set(key, String(value));
    const doc = STORAGE_DOCS[key as WorkbenchStorageKey];
    if (!doc) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(value);
    } catch {
      parsed = value;
    }
    this.pendingWrites = this.pendingWrites.then(async () => {
      const response = await fetch(`/api/state/${doc}`, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (response.status === 401) {
        redirectToLogin();
        return;
      }
      if (!response.ok) throw new Error(`State save failed: ${response.status}`);
    }).catch((error: unknown) => console.error(error));
  }

  reset(): Promise<void> {
    this.values.clear();
    return this.resetRemote();
  }

  private resetRemote(): Promise<void> {
    if (this.resetStarted) return this.pendingWrites;
    this.resetStarted = true;
    this.pendingWrites = this.pendingWrites.then(async () => {
      const response = await fetch("/api/state", { method: "DELETE", credentials: "same-origin" });
      if (response.status === 401) {
        redirectToLogin();
        return;
      }
      if (!response.ok) throw new Error(`State reset failed: ${response.status}`);
    }).catch((error: unknown) => console.error(error)).finally(() => {
      this.resetStarted = false;
    });
    return this.pendingWrites;
  }
}

function redirectToLogin(): void {
  const returnTo = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
}

let workbenchStorage: Storage | undefined;

export function getWorkbenchStorage(): Storage {
  return workbenchStorage ?? window.localStorage;
}

export function setWorkbenchStorage(storage: Storage): void {
  workbenchStorage = storage;
}
