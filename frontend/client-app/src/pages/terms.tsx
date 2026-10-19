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
            <span className="font-semibold text-gray-900">Thistlecombe Mutual</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Terms of Service</h1>
        <p className="text-xs text-gray-400 mb-6">
          Fictional legal document — {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Acceptance of Terms.</strong>{" "}
            By accessing the Thistlecombe workspace, you agree to use it for
            authorized policy and claims work. This fictional service is for
            demonstration purposes only.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            Staff and agents may use the workspace to manage policies, claims
            and related documents. Use must follow company procedures and
            applicable law.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> You are
            responsible for protecting your sign-in details and promptly
            reporting suspected unauthorized access.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Thistlecombe Mutual may suspend accounts for misuse of the
            workspace or violations of company procedures.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            terms are fictional and do not create a contract or provide
            insurance coverage.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
