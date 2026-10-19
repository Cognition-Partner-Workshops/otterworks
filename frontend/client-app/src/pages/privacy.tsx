import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { Logo } from "@/components/ui/logo";
import { COMPANY } from "@/lib/corporate";

export default function PrivacyPage() {
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
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Privacy Policy</h1>
        <p className="text-xs text-gray-400 mb-6">
          Demo policy only. {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Account information.</strong>{" "}
            The demo stores a user name, email address, and account credentials
            needed to sign in.
          </p>
          <p>
            <strong className="text-gray-900">2. Utility records.</strong>{" "}
            Work orders, switching plans, inspection photos, and meter records
            are handled as demo data. Do not enter customer or system data.
          </p>
          <p>
            <strong className="text-gray-900">3. Access.</strong>{" "}
            Users can share work packs with people who need them. Audit records
            show access and changes in the demo workspace.
          </p>
          <p>
            <strong className="text-gray-900">4. Retention.</strong>{" "}
            Deleted records remain in Trash for thirty days in the demo.
          </p>
          <p>
            <strong className="text-gray-900">5. Contact.</strong>{" "}
            Questions about the demo can be sent to Customer Care at{" "}
            {COMPANY.headquarters}.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
