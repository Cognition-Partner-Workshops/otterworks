import type { Metadata } from "next";
import { Inter, Fraunces } from "next/font/google";
import { BagProvider } from "@/components/BagProvider";
import { FavoritesProvider } from "@/components/FavoritesProvider";
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
        <a href="#main" className="sr-only z-50 bg-teal px-4 py-2 text-white focus:not-sr-only focus:fixed focus:left-2 focus:top-2">Skip to content</a>
        <BagProvider>
          <FavoritesProvider>
            <PromoBanner promo={promo} />
            <Header />
            <main id="main" tabIndex={-1} className="min-h-[60vh] focus:outline-none">{children}</main>
            <Footer />
            <MiniBag />
          </FavoritesProvider>
        </BagProvider>
      </body>
    </html>
  );
}
