export function PreviewLoading() {
  return (
    <div role="status" aria-label="Loading preview" className="py-8">
      <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-otter-600 border-t-transparent" />
    </div>
  );
}
