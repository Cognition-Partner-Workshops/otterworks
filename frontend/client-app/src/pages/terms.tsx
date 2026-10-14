import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { BrandLockup } from "@/components/ui/brand-lockup";
import { COMPANY } from "@/lib/corporate";
import { ConceptBanner } from "@/components/layout/concept-banner";

export default function TermsPage() {
  return (
    <main className="flex min-h-screen flex-col bg-[#f5f5f5]">
      <ConceptBanner />
      <header className="border-b border-[#ddd] bg-white">
        <div className="mx-auto flex min-h-16 max-w-4xl items-center px-4 py-3">
          <Link to="/" aria-label="Bank of America Document Center home">
            <BrandLockup />
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
            By accessing Document Center you agree to use it only for authorized
            business purposes. These terms are part of a concept demo and carry
            no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store files, edit documents and collaborate with colleagues.
            You may not upload data you are not authorized to hold or share
            documents outside your entitlements.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> You are
            responsible for your credentials. Report suspected unauthorized
            access to Information Security immediately.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Access may be suspended for policy violations or role changes.
            Suspensions can be appealed through your manager.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            Concept demo only; no governing law applies.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
