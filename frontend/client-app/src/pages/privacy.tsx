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
            <span className="font-serif font-semibold text-gray-900">Halvergate Bank</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Privacy Policy</h1>
        <p className="text-xs text-gray-400 mb-6">
          Fictional legal document. {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Information We Collect.</strong>{" "}
            Halvergate stores the account records, loan files and documents your team uploads, along with your display name and work email address.
          </p>
          <p>
            <strong className="text-gray-900">2. How We Use It.</strong>{" "}
            We use this data to run the service: storage, sharing, search and notifications. We do not sell customer or employee data.
          </p>
          <p>
            <strong className="text-gray-900">3. Sharing.</strong>{" "}
            Records are shared only with the colleagues you add. Audit logs record every access so the compliance team can answer examiner requests.
          </p>
          <p>
            <strong className="text-gray-900">4. Retention.</strong>{" "}
            Deleted items stay in the Trash for thirty days and are then removed. Records under a legal hold are kept until the hold is released.
          </p>
          <p>
            <strong className="text-gray-900">5. Contact.</strong>{" "}
            Send questions to the Risk &amp; Compliance department at {COMPANY.headquarters}.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
