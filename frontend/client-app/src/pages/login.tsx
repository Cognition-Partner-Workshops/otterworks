import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, LogIn } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { BrandLockup } from "@/components/ui/brand-lockup";
import { ConceptBanner } from "@/components/layout/concept-banner";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const { setUser } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setLoading(true);
    setError("");
    try {
      const tokens = await authApi.login(data);
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
      const user = await authApi.getProfile();
      setUser(user);
      navigate("/dashboard");
    } catch {
      setError("Invalid email or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

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

            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-sm font-medium text-gray-700"
                >
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  {...register("email")}
                  className="w-full rounded-[4px] border border-[#333] px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-otter-500 focus:border-transparent transition"
                  placeholder="you@example.com"
                />
                {errors.email && (
                  <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>
                )}
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="mb-1.5 block text-sm font-medium text-gray-700"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    {...register("password")}
                    className="w-full rounded-[4px] border border-[#333] px-3 py-3 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-otter-500 focus:border-transparent transition"
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-1 text-xs text-red-500">{errors.password.message}</p>
                )}
              </div>

              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 bg-otter-600 text-sm text-white disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {loading ? (
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <>
                    <LogIn size={18} />
                    Sign in
                  </>
                )}
              </button>
            </form>
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
