export function resetWorkbenchData(storage: Storage = window.localStorage): void {
  for (let index = storage.length - 1; index >= 0; index -= 1) {
    const key = storage.key(index);
    if (key?.startsWith("workbench.")) storage.removeItem(key);
  }
}
