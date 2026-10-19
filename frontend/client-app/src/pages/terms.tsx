import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { Logo } from "@/components/ui/logo";
import { COMPANY } from "@/lib/corporate";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-otter-50 flex flex-col">
      <header className="bg-white border-b border-gray-300">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2">
            <Logo size={28} />
            <span className="font-semibold text-gray-900">Pennant Lane, Inc.</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Terms of Service</h1>
        <p className="text-xs text-gray-400 mb-6">
          Fictional legal document: {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Store accounts.</strong>{" "}
            By using the Pennant Lane store workspace you agree to use it for
            company business only. Store accounts belong to the associate they
            were issued to, so do not share a sign-in across shifts.
          </p>
          <p>
            <strong className="text-gray-900">2. Confidentiality.</strong>{" "}
            Files posted here (planograms, price files, ad proofs) stay company
            confidential until the ad week starts. Do not forward them to
            vendors or post them outside the company.
          </p>
          <p>
            <strong className="text-gray-900">3. Account suspension.</strong>{" "}
            Pennant Lane, Inc. may suspend an account that breaks these rules.
            Talk to your store manager or the support center help desk if you
            think a suspension is wrong.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
