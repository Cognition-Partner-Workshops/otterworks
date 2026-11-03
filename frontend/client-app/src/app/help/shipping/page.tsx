export const metadata = { title: "Shipping" };

export default function Page() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10 text-neutral-800">
      <h1 className="font-display text-3xl font-bold text-ink">Shipping</h1>
      <div className="mt-6 space-y-4 leading-relaxed"><p>Standard shipping is $7.99 and arrives in 5-7 business days. It is free on orders of $50 or more after discounts.</p><p>Express shipping is $19.99 and arrives in 2 business days.</p><p>Free store pickup is available at most stores and is usually ready within 1-4 hours. Colorado orders include the state retail delivery fee. California pickup orders include a 10 cent bag fee.</p></div>
    </article>
  );
}
