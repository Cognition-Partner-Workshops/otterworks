import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { BrandLockup } from "@/components/ui/brand-lockup";
import { COMPANY } from "@/lib/corporate";
import { ConceptBanner } from "@/components/layout/concept-banner";

export default function PrivacyPage() {
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
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Privacy Policy</h1>
        <p className="text-xs text-gray-400 mb-6">
          Fictional legal document — {COMPANY.disclaimer}
        </p>
        <div className="bg-white border border-gray-300 rounded p-6 space-y-4 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong className="text-gray-900">1. Information We Collect.</strong>{" "}
            Document Center stores the files and documents you upload, your
            display name, and your work email address.
          </p>
          <p>
            <strong className="text-gray-900">2. How We Use It.</strong> Your
            Data is used only to operate the service: storage, sharing, search
            and notifications. It is never sold or used for advertising.
          </p>
          <p>
            <strong className="text-gray-900">3. Sharing.</strong> Content is
            shared only with colleagues you explicitly authorize. Audit logs
            record every access for compliance review.
          </p>
          <p>
            <strong className="text-gray-900">4. Retention.</strong> Deleted
            items stay in Trash for thirty days before permanent deletion,
            unless a legal hold applies.
          </p>
          <p>
            <strong className="text-gray-900">5. Contact.</strong> Questions?
            Write to the Records &amp; Compliance department at {COMPANY.headquarters}.
          </p>
        </div>
      </div>
      <Footer />
    </main>
  );
}
