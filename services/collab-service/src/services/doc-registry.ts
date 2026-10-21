import * as Y from 'yjs';
import { DocumentStore } from './document-store';
import { MetricsCollector } from '../metrics';

export interface DocRegistryDeps {
  documentStore: DocumentStore;
  metrics: MetricsCollector;
}

/** In-memory registry of live Yjs documents, hydrated from the document store on first use. */
export class DocRegistry {
  private documents: Map<string, Y.Doc> = new Map();
  private documentInitPromises: Map<string, Promise<Y.Doc>> = new Map();
  private deps: DocRegistryDeps;

  constructor(deps: DocRegistryDeps) {
    this.deps = deps;
  }

  get(documentId: string): Y.Doc | undefined {
    return this.documents.get(documentId);
  }

  get size(): number {
    return this.documents.size;
  }

  entries(): IterableIterator<[string, Y.Doc]> {
    return this.documents.entries();
  }

  async getOrCreate(documentId: string): Promise<Y.Doc> {
    const existing = this.documents.get(documentId);
    if (existing) return existing;

    const pending = this.documentInitPromises.get(documentId);
    if (pending) return pending;

    const { documentStore, metrics } = this.deps;
    const initPromise = (async () => {
      try {
        const doc = new Y.Doc();
        const savedState = await documentStore.getDocumentState(documentId);
        if (savedState) {
          Y.applyUpdate(doc, savedState);
        }
        this.documents.set(documentId, doc);
        metrics.activeRooms.inc();
        return doc;
      } finally {
        this.documentInitPromises.delete(documentId);
      }
    })();

    this.documentInitPromises.set(documentId, initPromise);
    return initPromise;
  }

  remove(documentId: string): boolean {
    const removed = this.documents.delete(documentId);
    if (removed) {
      this.deps.metrics.activeRooms.dec();
    }
    return removed;
  }
}
