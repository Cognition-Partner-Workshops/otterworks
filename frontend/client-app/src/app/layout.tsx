import type { Metadata } from "next";
import { Inter, Fraunces } from "next/font/google";
import { BagProvider } from "@/components/BagProvider";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { MiniBag } from "@/components/MiniBag";
import { PromoBanner } from "@/components/PromoBanner";
import { api } from "@/lib/api";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const display = Fraunces({ subsets: ["latin"], variable: "--font-display", weight: ["600", "700"] });

export const metadata: Metadata = {
  title: { default: "OtterShops | Everyday clothes for the whole family", template: "%s | OtterShops" },
  description: "OtterShops is a fictional apparel store built for demos.",
};

export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const promo = await api.promotion();
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body className="font-sans">
        <BagProvider>
          <PromoBanner promo={promo} />
          <Header />
          <main className="min-h-[60vh]">{children}</main>
          <Footer />
          <MiniBag />
        </BagProvider>
      </body>
    </html>
  );
}
