import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center">
      <h1 className="font-display text-3xl font-bold">We couldn&apos;t find that page</h1>
      <Link href="/" className="btn mt-6">Back to home</Link>
    </div>
  );
}
