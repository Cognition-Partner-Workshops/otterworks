export function Spinner() {
  return (
    <div className="flex justify-center p-[60px]">
      <span
        role="progressbar"
        aria-label="Loading"
        className="block h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-[#1976d2]"
      />
    </div>
  );
}
