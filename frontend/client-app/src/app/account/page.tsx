"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useBag } from "@/components/BagProvider";
import { call } from "@/lib/client";
import { money } from "@/lib/format";
import type { Customer, OrderSummary } from "@/lib/types";

export default function AccountPage() {
  const { customer, ready, signOut } = useBag();
  const router = useRouter();
  const [data, setData] = useState<{ customer: Customer; orders: OrderSummary[] } | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!customer) {
      router.replace("/account/sign-in?next=/account");
      return;
    }
    call<{ customer: Customer; orders: OrderSummary[] }>("/account").then(setData).catch(() => router.replace("/account/sign-in?next=/account"));
  }, [ready, customer, router]);

  if (!data) return <div className="mx-auto max-w-4xl px-4 py-12">Loading your account...</div>;
  const c = data.customer;
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold">Hi, {c.firstName}</h1>
          <p className="mt-1 text-sm text-neutral-600">{c.email} · Member since {new Date(c.createdAt).toLocaleDateString()}</p>
        </div>
        <button type="button" onClick={async () => { await signOut(); router.push("/"); }} className="text-sm underline" data-testid="sign-out">Sign out</button>
      </div>
      <section className="mt-8 flex items-center justify-between bg-teal p-6 text-white" data-testid="rewards">
        <div>
          <p className="text-sm uppercase tracking-wide">OtterShops Rewards</p>
          <p className="mt-1 text-4xl font-bold"><span data-testid="rewards-points">{c.rewardsPoints}</span> points</p>
        </div>
        <p className="max-w-xs text-sm">1 point for every $1. Every 500 points is a $5 reward.</p>
      </section>
      <section className="mt-10">
        <h2 className="text-xl font-semibold">Order history</h2>
        {data.orders.length === 0 ? (
          <p className="mt-3 text-sm text-neutral-600">No orders yet. <Link href="/" className="underline">Start shopping</Link></p>
        ) : (
          <ul className="mt-4 divide-y border-y" data-testid="order-history">
            {data.orders.map((o) => (
              <li key={o.orderNumber}>
                <Link href={`/account/orders/${o.orderNumber}`} className="flex items-center gap-4 py-4 hover:bg-sand">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {o.image && <img src={o.image.replace(".webp", "-sm.webp")} alt="" className="h-16 w-12 object-cover" />}
                  <div className="flex-1 text-sm">
                    <p className="font-semibold">{o.orderNumber}</p>
                    <p className="text-neutral-600">{new Date(o.createdAt).toLocaleDateString()} · {o.itemCount} item{o.itemCount === 1 ? "" : "s"} · {o.fulfillment === "PICKUP" ? "Store pickup" : "Shipped"}</p>
                  </div>
                  <p className="text-sm font-semibold">{money(o.totalCents)}</p>
                  <span className="text-xs text-teal">{o.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
