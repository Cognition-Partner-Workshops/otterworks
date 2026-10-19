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
            <span className="font-serif font-semibold text-gray-900">Halvergate Bank</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Terms of Service</h1>
        <p className="text-xs text-gray-400 mb-6">
          Fictional legal document. {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Acceptance of Terms.</strong>{" "}
            By using the Halvergate records system you agree to these terms. They are fictional and carry no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            Use the service to store account records, draft credit memos and work with colleagues. Keep customer data in bank folders and share it only with people inside the bank.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong>{" "}
            Keep your password to yourself and report any sign-in you don't recognize to the service desk the same day.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Halvergate Bank may suspend an account that breaks bank policy. Suspended users can appeal through their branch or department manager.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong>{" "}
            These terms fall under the fictional banking statutes of the State of Ashford.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
