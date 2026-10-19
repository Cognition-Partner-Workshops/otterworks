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
            <span className="font-semibold text-gray-900">Hollinmere</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Terms of Service</h1>
        <p className="text-xs text-gray-400 mb-6">
          Demo terms only. {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Demo use.</strong>{" "}
            This fictional service demonstrates records for utility operations.
            The page does not create a contract or change an electric service
            agreement.
          </p>
          <p>
            <strong className="text-gray-900">2. Work records.</strong>{" "}
            Demo users can store work orders, line drawings, inspection photos,
            and switching plans. Use sample information only.
          </p>
          <p>
            <strong className="text-gray-900">3. Accounts.</strong>{" "}
            Each user is responsible for keeping account credentials private.
            Contact the utility administrator if access appears incorrect.
          </p>
          <p>
            <strong className="text-gray-900">4. Service status.</strong>{" "}
            Outage notices, meter reads, and crew assignments in this demo are
            sample records. They do not report live grid conditions.
          </p>
          <p>
            <strong className="text-gray-900">5. Fictional operator.</strong>{" "}
            Hollinmere Power &amp; Light and the Hollin Valley are fictional.
            These terms have no legal force.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
