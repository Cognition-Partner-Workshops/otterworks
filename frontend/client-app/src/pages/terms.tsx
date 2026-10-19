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
            <span className="font-semibold text-gray-900">Tamberlyn Pictures</span>
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
            By signing in to the Tamberlyn studio workspace, you agree to
            these terms. They are fictional and carry no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store production files, edit scripts and documents, and
            share them with your crew. Don't upload titles you don't hold
            rights to, and don't share masters outside the people a contract
            names.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> You are
            responsible for your password. Tell Studio Services right away if
            you think someone else has used your account.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Tamberlyn Pictures may suspend an account when a production wraps
            or a contract ends. You can ask Studio Services to review it.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            terms are governed by the fictional laws of Port Calder.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
