import { OrderDetail } from "@/components/OrderDetail";

export const metadata = { title: "Order details" };

export default async function AccountOrderPage({ params }: { params: Promise<{ number: string }> }) {
  return <OrderDetail number={(await params).number} />;
}
