import Link from "next/link";

const cols = [
  { title: "Help", links: [["Help center", "/help"], ["Track an order", "/order-lookup"], ["Shipping", "/help/shipping"], ["Returns", "/help/returns"], ["Size guide", "/help/size-guide"], ["Contact us", "/help/contact"]] },
  { title: "Shop", links: [["Rewards", "/rewards"], ["Gift cards & balance", "/gift-cards"], ["Find a store", "/stores"], ["Favorites", "/favorites"], ["Sale", "/sale"]] },
  { title: "OtterShops", links: [["About", "/about"], ["My account", "/account"], ["Accessibility", "/accessibility"], ["Privacy", "/privacy"], ["Terms of use", "/terms"]] },
];

export function Footer() {
  return (
    <footer className="mt-16 border-t border-neutral-200 bg-sand" aria-label="Site footer">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-4">
        {cols.map((c) => (
          <div key={c.title}>
            <h2 className="mb-3 text-sm font-semibold">{c.title}</h2>
            <ul className="space-y-2 text-sm">
              {c.links.map(([label, href]) => (
                <li key={href}><Link href={href} className="hover:underline">{label}</Link></li>
              ))}
            </ul>
          </div>
        ))}
        <div className="text-sm text-neutral-600">
          <p className="font-display text-xl font-bold text-teal">OtterShops</p>
          <p className="mt-2">Everyday clothes for the whole family.</p>
        </div>
      </div>
      <p className="border-t border-neutral-200 py-4 text-center text-xs text-neutral-500">
        OtterShops is a fictional demo store. No real orders are placed and no cards are charged. Photos from Unsplash.
      </p>
    </footer>
  );
}
