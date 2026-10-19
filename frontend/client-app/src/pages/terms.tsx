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
            <span className="font-semibold text-gray-900">Quillstead Capital</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Terms of Service</h1>
        <p className="text-xs text-gray-400 mb-6">
          {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Acceptance of Terms.</strong>{" "}
            By using this service, you agree to use it for lawful client, portfolio,
            research, and brokerage operations. These terms are fictional and do
            not create a legal agreement.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store client files, edit research notes, and collaborate with
            authorized colleagues. Keep account credentials private and use the
            service only for permitted business purposes.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> You are
            responsible for safeguarding your password and activity under your
            account. Report suspected unauthorized access to your administrator.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Quillstead Capital may suspend an account used outside these terms.
            A formal appeal process is outside this fictional service.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            Quillstead Capital is fictional, so the terms name no real jurisdiction.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
