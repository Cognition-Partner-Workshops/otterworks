export const metadata = { title: "Privacy" };

export default function Page() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10 text-neutral-800">
      <h1 className="font-display text-3xl font-bold text-ink">Privacy</h1>
      <div className="mt-6 space-y-4 leading-relaxed"><p>OtterShops is a fictional demo store. We store only what the demo needs to work: your bag, favorites, orders, saved addresses and the reviews you write. Passwords are hashed, and card numbers are never stored; only the brand and last four digits are kept.</p><p>Back-in-stock alerts use the email you give us for that item only. No email is actually sent.</p></div>
    </article>
  );
}
