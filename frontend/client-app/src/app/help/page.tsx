import Link from "next/link";

export const metadata = { title: "Help center" };

const topics = [
  { title: "Track an order", body: "Order number and email are all you need.", href: "/order-lookup" },
  { title: "Start a return", body: "Free returns by mail or in store within 45 days.", href: "/help/returns" },
  { title: "Shipping", body: "Free standard shipping on orders of $50 or more.", href: "/help/shipping" },
  { title: "Size guide", body: "Measurements for women, men, kids and baby.", href: "/help/size-guide" },
  { title: "Gift card balance", body: "Check what's left on a card.", href: "/gift-cards" },
  { title: "Contact us", body: "Phone and email, 7am to 10pm Eastern.", href: "/help/contact" },
];

const faqs = [
  ["Can I change my order?", "Orders start processing about two minutes after you place them. After that, return what you don't need."],
  ["When is pickup ready?", "Most stores have pickup orders ready in two hours. We'll show the time on your order page."],
  ["Do sale items qualify for free returns?", "Yes. Gift cards are the only final-sale item."],
  ["How do back-in-stock alerts work?", "Choose a sold-out size on the product page and leave your email. One alert per size."],
];

export default function Page() {
  return (
    <article className="mx-auto max-w-5xl px-4 py-10 text-neutral-800">
      <h1 className="font-display text-3xl font-bold text-ink">How can we help?</h1>
      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {topics.map((t) => (
          <li key={t.href}>
            <Link href={t.href} className="block h-full border p-4 hover:border-teal focus:border-teal">
              <h2 className="font-semibold">{t.title}</h2>
              <p className="mt-1 text-sm text-neutral-600">{t.body}</p>
            </Link>
          </li>
        ))}
      </ul>
      <h2 className="mt-10 text-xl font-semibold">Common questions</h2>
      <div className="mt-4 divide-y border-y">
        {faqs.map(([q, a]) => (
          <details key={q} className="py-3">
            <summary className="cursor-pointer font-medium">{q}</summary>
            <p className="mt-2 text-sm text-neutral-700">{a}</p>
          </details>
        ))}
      </div>
    </article>
  );
}
