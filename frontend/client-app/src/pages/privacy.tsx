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
            <span className="font-semibold text-gray-900">Quillstead Capital</span>
          </Link>
        </div>
      </header>
      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Privacy Policy</h1>
        <p className="text-xs text-gray-400 mb-6">
          {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Information We Collect.</strong>{" "}
            Quillstead Capital stores client files and research notes uploaded to
            this service, along with account names and email addresses.
          </p>
          <p>
            <strong className="text-gray-900">2. How We Use It.</strong> Your
            data supports file storage, sharing, search, notifications, and account
            administration. Quillstead Capital does not sell account data.
          </p>
          <p>
            <strong className="text-gray-900">3. Sharing.</strong> Content is
            shared with the people selected by the account holder. Audit records
            capture access and administrative activity.
          </p>
          <p>
            <strong className="text-gray-900">4. Retention.</strong> Deleted
            items remain in Trash for thirty days before permanent deletion.
          </p>
          <p>
            <strong className="text-gray-900">5. Contact.</strong> Contact
            Compliance &amp; Risk at {COMPANY.headquarters} with questions.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
