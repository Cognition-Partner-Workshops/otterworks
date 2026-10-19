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
            By using Halvenmoor Health online services you agree to these terms.
            The terms are fictional and carry no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store files, edit care notes and work with your care team.
            Don't upload another member's records without their consent, and
            don't try to open accounts that aren't yours.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong>{" "}
            Keep your password private. Tell Member Services right away if you
            think someone else has signed in to your account.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Halvenmoor Health may suspend accounts that put member data at risk.
            You can appeal a suspension through Member Services.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            terms are governed by the fictional laws of Larch County.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
