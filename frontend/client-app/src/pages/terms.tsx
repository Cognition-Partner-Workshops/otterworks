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
            <span className="font-semibold text-gray-900">Halvorne Biosciences, Inc.</span>
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
            By using Halvorne you agree to follow the company SOPs for records, including the GxP rules for anything that supports a regulatory filing. These terms are fictional and have no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store study files, edit controlled documents and work with colleagues on reviews. Keep patient-identifying data inside an approved study folder, and share unblinded data only with the unblinded team named in the protocol.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> Your account and electronic signature belong to you alone, so never share your password. Report any access you did not make to IT Security the same day.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Halvorne Biosciences, Inc. may suspend accounts that break these terms. Quality Assurance reviews every suspension.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            terms are governed by the fictional laws of the state of Aldermoor.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
