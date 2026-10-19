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
            <span className="font-semibold text-gray-900">Vetchline Software, Inc.</span>
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
            By using Vetchline, your organization agrees to these terms on
            behalf of every member of its workspace. These terms are fictional
            and carry no legal force.
          </p>
          <p>
            <strong className="text-gray-900">2. Use of the Service.</strong>{" "}
            You may store files, edit documents, and collaborate with people
            your workspace invites. You may not probe other workspaces, run
            load tests against production, or resell access.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong> Workspace
            owners manage who has access. Tell us within 24 hours if you see a
            login you don't recognize.
          </p>
          <p>
            <strong className="text-gray-900">4. Termination.</strong>{" "}
            Vetchline Software, Inc. may suspend a workspace for abuse or
            non-payment after 14 days' written notice to the workspace owner.
          </p>
          <p>
            <strong className="text-gray-900">5. Governing Law.</strong> These
            terms are governed by the fictional statutes of Harlow Point.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
