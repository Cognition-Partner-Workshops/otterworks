import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, UserPlus } from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { BrandLockup } from "@/components/ui/brand-lockup";
import { ConceptBanner } from "@/components/layout/concept-banner";

const registerSchema = z
  .object({
    displayName: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Please enter a valid email"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const navigate = useNavigate();
  const { setUser } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterForm) => {
    setLoading(true);
    setError("");
    try {
      const tokens = await authApi.register(data);
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
      const user = await authApi.getProfile();
      setUser(user);
      navigate("/dashboard");
    } catch {
      setError("Registration failed. This email may already be in use.");
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
              Create your account
            </h1>

            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              <div>
                <label
                  htmlFor="name"
                  className="mb-1.5 block text-sm font-medium text-gray-700"
                >
                  Full name
                </label>
                <input
                  id="name"
                  type="text"
                  {...register("displayName")}
                  className="w-full rounded-[4px] border border-[#333] px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-otter-500 focus:border-transparent transition"
                  placeholder="Jane Smith"
                />
                {errors.displayName && (
                  <p className="mt-1 text-xs text-red-500">{errors.displayName.message}</p>
                )}
              </div>

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
                    placeholder="At least 8 characters"
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

              <div>
                <label
                  htmlFor="confirmPassword"
                  className="mb-1.5 block text-sm font-medium text-gray-700"
                >
                  Confirm password
                </label>
                <div className="relative">
                  <input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    {...register("confirmPassword")}
                    className="w-full rounded-[4px] border border-[#333] px-3 py-3 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-otter-500 focus:border-transparent transition"
                    placeholder="Repeat your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="mt-1 text-xs text-red-500">
                    {errors.confirmPassword.message}
                  </p>
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
                    <UserPlus size={18} />
                    Create account
                  </>
                )}
              </button>
            </form>
          </div>

          <p className="mt-6 text-center text-sm text-white">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-white underline">
              Sign in
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
