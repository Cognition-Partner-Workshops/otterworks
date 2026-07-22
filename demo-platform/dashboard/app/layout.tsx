import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Careotter Demo Ops",
  description: "Ops dashboard for Careotter ephemeral demo tenants",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
