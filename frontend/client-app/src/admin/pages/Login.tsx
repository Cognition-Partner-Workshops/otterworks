import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { login } from "../auth";
import otterLogo from "@/assets/otter-logo.png";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [hidden, setHidden] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  if (localStorage.getItem("ow_admin_token"))
    return <Navigate to="/admin" replace />;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await login(email, password);
      navigate("/admin");
    } catch (error) {
      setLoading(false);
      setError(
        error instanceof Error
          ? error.message
          : "Login failed. Please try again."
      );
    }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#1f3a5f]">
      <section className="w-[420px] rounded bg-white p-10 shadow">
        <div className="mb-6 text-center">
          <img
            src={otterLogo}
            alt="OtterWorks logo"
            width={64}
            height={64}
            className="mx-auto mb-4"
          />
          <h1 className="text-2xl">OtterWorks Admin</h1>
          <p className="mt-2 text-gray-500">Sign in to the admin dashboard</p>
        </div>
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <label>
            Email
            <input
              type="email"
              value={email}
              placeholder="admin@otterworks.io"
              onChange={(e) => {
                setEmail(e.target.value);
                setError("");
              }}
              className="mt-1 w-full rounded border p-3"
            />
          </label>
          <label>
            Password
            <span className="mt-1 flex rounded border">
              <input
                type={hidden ? "password" : "text"}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setError("");
                }}
                className="min-w-0 flex-1 p-3"
              />
              <button
                type="button"
                aria-label={hidden ? "Show password" : "Hide password"}
                onClick={() => setHidden(!hidden)}
                className="px-3"
              >
                {hidden ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </span>
          </label>
          {error && (
            <p role="alert" className="text-red-500">
              {error}
            </p>
          )}
          <button
            disabled={loading}
            className="h-12 rounded bg-[#1976d2] text-base text-white disabled:opacity-60"
          >
            {loading ? (
              <span
                role="progressbar"
                aria-label="Signing in"
                className="mx-auto block h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"
              />
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      </section>
    </div>
  );
}
