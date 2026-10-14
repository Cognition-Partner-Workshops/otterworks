import { Link } from "react-router-dom";
import { BrandLockup } from "@/components/ui/brand-lockup";
import { ConceptBanner } from "@/components/layout/concept-banner";
import { SignInForm } from "@/components/auth/sign-in-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col bg-[#f5f5f5]">
      <ConceptBanner />
      <header className="border-b border-[#ddd] bg-white">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center px-4 py-3">
          <Link to="/" aria-label="Bank of America Document Center home">
            <BrandLockup />
          </Link>
        </div>
      </header>
      <main className="bank-gradient flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-lg">
          <div className="rounded-[8px] border border-gray-200 bg-white p-6 shadow-lg sm:p-8">
            <h1 className="mb-6 text-xl font-semibold text-[#012169]">
              Sign in to your account
            </h1>

            <SignInForm />
          </div>

          <p className="mt-6 text-center text-sm text-white">
            Don&apos;t have an account?{" "}
            <Link to="/register" className="font-medium text-white underline">
              Create one
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
