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
            <span className="font-semibold text-gray-900">{COMPANY.name}</span>
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
            By using Brassmoor's engineering workspace you agree to these
            terms. They are fictional and carry no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store drawings, edit specs and work with other engineers,
            inspectors and approved suppliers. Do not upload export-controlled
            data to a folder shared outside the company.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> Keep your
            password to yourself, and tell IT right away if you think someone
            else has used your account.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Brassmoor Industries may suspend accounts that break these terms or
            the plant's document control procedure.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            terms follow the fictional statutes of Millbrook County.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
