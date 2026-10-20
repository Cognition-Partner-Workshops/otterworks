import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import thistlecombeMark from "@client-app/assets/thistlecombe-mark.svg";
import { api, type Source } from "./api";
import { FnolIntake } from "./pages/fnol-intake";
import { ClaimStatusPage } from "./pages/claim-status";
import { PaymentConfirmation } from "./pages/payment-confirmation";

const NAV = [
  { to: "/", label: "FNOL intake" },
  { to: "/claims", label: "Claim status" },
  { to: "/payments", label: "Payment confirmation" },
];

export function App() {
  const [source, setSource] = useState<Source | null>(null);
  useEffect(() => { api.source().then(setSource).catch(() => setSource(null)); }, []);

  return (
    <div className="min-h-screen bg-otter-50">
      <header className="bg-otter-800 text-white">
        <div className="max-w-5xl mx-auto flex items-center gap-3 px-4 h-12">
          <img src={thistlecombeMark} alt="Thistlecombe Mutual logo" width={28} height={28} />
          <span className="text-sm font-semibold tracking-wide">Thistlecombe Mutual</span>
          <span className="text-otter-300">/</span>
          <span className="text-sm">Claims</span>
          <nav className="ml-6 flex gap-1">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === "/"}
                className={({ isActive }) => `px-3 py-1 text-sm rounded ${isActive ? "bg-otter-600 text-white" : "text-otter-100 hover:bg-otter-700"}`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <div data-testid="source-banner"
        className={`border-b text-xs ${source?.source === "camel" ? "bg-accent-400/20 border-accent-400 text-accent-600" : "bg-white border-gray-300 text-gray-600"}`}>
        <div className="max-w-5xl mx-auto px-4 py-1.5">
          Behind these screens: <strong>{source ? source.label : "API unreachable"}</strong>
          {source && <span className="ml-2 text-gray-500">({source.detail})</span>}
        </div>
      </div>
      <main className="max-w-5xl mx-auto p-4 lg:p-5">
        <Routes>
          <Route path="/" element={<FnolIntake />} />
          <Route path="/claims" element={<ClaimStatusPage />} />
          <Route path="/claims/:claim" element={<ClaimStatusPage />} />
          <Route path="/payments" element={<PaymentConfirmation />} />
          <Route path="/payments/:id" element={<PaymentConfirmation />} />
        </Routes>
      </main>
    </div>
  );
}
