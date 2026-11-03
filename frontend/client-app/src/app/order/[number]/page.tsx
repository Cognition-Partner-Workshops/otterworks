import { OrderDetail } from "@/components/OrderDetail";

export const metadata = { title: "Order confirmation" };

export default async function OrderPage({ params, searchParams }: { params: Promise<{ number: string }>; searchParams: Promise<{ email?: string; placed?: string }> }) {
  const [{ number }, sp] = await Promise.all([params, searchParams]);
  return <OrderDetail number={number} email={sp.email} placed={sp.placed === "1"} />;
}
