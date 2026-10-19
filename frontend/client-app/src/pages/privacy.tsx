import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { Logo } from "@/components/ui/logo";
import { COMPANY } from "@/lib/corporate";

export default function PrivacyPage() {
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
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Privacy Policy</h1>
        <p className="text-xs text-gray-400 mb-6">
          Fictional legal document. {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Information We Collect.</strong>{" "}
            The department stores the case files and records you upload, your
            name and email address, and an audit log of who opened each record.
          </p>
          <p>
            <strong className="text-gray-900">2. How We Use It.</strong> The
            department uses case information to operate its case, permit and
            records services.
          </p>
          <p>
            <strong className="text-gray-900">3. Sharing.</strong> Records are
            shared only with staff assigned to your case or with agencies the
            law allows.
          </p>
          <p>
            <strong className="text-gray-900">4. Retention.</strong> Records
            are kept according to the state retention schedule.
          </p>
          <p>
            <strong className="text-gray-900">5. Contact.</strong> Contact the
            Department of Resident Services at {COMPANY.headquarters}.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
