import * as Y from 'yjs';
import { DocRegistry } from '../services/doc-registry';
import { DocumentStore } from '../services/document-store';
import { MetricsCollector } from '../metrics';

function encodeText(text: string): Uint8Array {
  const doc = new Y.Doc();
  doc.getText('content').insert(0, text);
  return Y.encodeStateAsUpdate(doc);
}

describe('DocRegistry', () => {
  let getDocumentState: jest.Mock;
  let metrics: MetricsCollector;
  let registry: DocRegistry;

  beforeEach(() => {
    getDocumentState = jest.fn().mockResolvedValue(null);
    metrics = new MetricsCollector();
    registry = new DocRegistry({
      documentStore: { getDocumentState } as unknown as DocumentStore,
      metrics,
    });
  });

  async function activeRooms(): Promise<number> {
    const metric = await metrics.activeRooms.get();
    return metric.values[0]?.value ?? 0;
  }

  it('returns undefined and size 0 for unknown documents', () => {
    expect(registry.get('missing')).toBeUndefined();
    expect(registry.size).toBe(0);
  });

  it('creates an empty doc when the store has no saved state', async () => {
    const doc = await registry.getOrCreate('doc-1');

    expect(getDocumentState).toHaveBeenCalledWith('doc-1');
    expect(doc.getText('content').toString()).toBe('');
    expect(registry.get('doc-1')).toBe(doc);
    expect(registry.size).toBe(1);
    expect(await activeRooms()).toBe(1);
  });

  it('hydrates a new doc from saved state', async () => {
    getDocumentState.mockResolvedValue(encodeText('persisted'));

    const doc = await registry.getOrCreate('doc-1');

    expect(doc.getText('content').toString()).toBe('persisted');
  });

  it('returns the cached doc without hitting the store again', async () => {
    const first = await registry.getOrCreate('doc-1');
    const second = await registry.getOrCreate('doc-1');

    expect(second).toBe(first);
    expect(getDocumentState).toHaveBeenCalledTimes(1);
    expect(await activeRooms()).toBe(1);
  });

  it('dedupes concurrent loads of the same document', async () => {
    let release: (value: Uint8Array | null) => void = () => {};
    getDocumentState.mockReturnValue(
      new Promise<Uint8Array | null>((resolve) => {
        release = resolve;
      }),
    );

    const pendingA = registry.getOrCreate('doc-1');
    const pendingB = registry.getOrCreate('doc-1');
    release(null);
    const [a, b] = await Promise.all([pendingA, pendingB]);

    expect(a).toBe(b);
    expect(getDocumentState).toHaveBeenCalledTimes(1);
    expect(await activeRooms()).toBe(1);
  });

  it('does not cache a doc when loading fails, and allows a retry', async () => {
    getDocumentState.mockRejectedValueOnce(new Error('redis down'));

    await expect(registry.getOrCreate('doc-1')).rejects.toThrow('redis down');
    expect(registry.get('doc-1')).toBeUndefined();
    expect(await activeRooms()).toBe(0);

    const doc = await registry.getOrCreate('doc-1');
    expect(registry.get('doc-1')).toBe(doc);
  });

  it('iterates all loaded documents', async () => {
    const a = await registry.getOrCreate('doc-a');
    const b = await registry.getOrCreate('doc-b');

    expect(Array.from(registry.entries())).toEqual([
      ['doc-a', a],
      ['doc-b', b],
    ]);
  });

  it('removes a loaded document and decrements active rooms', async () => {
    await registry.getOrCreate('doc-1');

    expect(registry.remove('doc-1')).toBe(true);
    expect(registry.get('doc-1')).toBeUndefined();
    expect(registry.size).toBe(0);
    expect(await activeRooms()).toBe(0);
  });

  it('ignores removal of unknown documents', async () => {
    expect(registry.remove('missing')).toBe(false);
    expect(await activeRooms()).toBe(0);
  });
});
