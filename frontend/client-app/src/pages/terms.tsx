import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { Logo } from "@/components/ui/logo";
import { COMPANY } from "@/lib/corporate";

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-[var(--background)] flex flex-col">
      <header className="bg-white border-b border-gray-300">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2">
            <Logo size={28} />
            <span className="font-semibold text-gray-900">Brindlemoor Department of Resident Services</span>
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
            Using the service means you accept these fictional terms. The terms
            carry no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            Use the service only for official department business or to manage
            your own case.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> Do not
            share your sign-in with anyone else.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            The department may suspend accounts that misuse case data.
            Suspended users may appeal to the Office of Administrative Hearings.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong>{" "}
            These terms are governed by fictional State of Brindlemoor law.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
