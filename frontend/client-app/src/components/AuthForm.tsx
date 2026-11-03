"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { HttpError } from "@/lib/client";
import { useBag } from "./BagProvider";

export function AuthForm({ mode }: { mode: "sign-in" | "register" }) {
  const { signIn, register } = useBag();
  const router = useRouter();
  const next = useSearchParams().get("next") ?? "/account";
  const [f, setF] = useState({ email: "", password: "", firstName: "", lastName: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "sign-in") await signIn(f.email, f.password);
      else await register(f);
      router.push(next.startsWith("/") ? next : "/account");
    } catch (err) {
      setError(err instanceof HttpError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  const input = (k: keyof typeof f, label: string, type = "text") => (
    <label className="block"><span className="label">{label}</span>
      <input required type={type} className="input" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`auth-${k}`} minLength={k === "password" ? 8 : undefined} />
    </label>
  );

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="font-display text-3xl font-bold">{mode === "sign-in" ? "Sign in" : "Create an account"}</h1>
      <p className="mt-2 text-sm text-neutral-600">Earn 1 point for every $1 and see your orders in one place. Items in your bag come with you.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {mode === "register" && <div className="grid grid-cols-2 gap-3">{input("firstName", "First name")}{input("lastName", "Last name")}</div>}
        {input("email", "Email", "email")}
        {input("password", "Password", "password")}
        {error && <p className="text-sm text-sale" role="alert">{error}</p>}
        <button type="submit" disabled={busy} className="btn w-full" data-testid="auth-submit">{mode === "sign-in" ? "Sign in" : "Create account"}</button>
      </form>
      {mode === "sign-in" ? (
        <>
          <p className="mt-4 text-sm">New here? <Link href={`/account/register?next=${encodeURIComponent(next)}`} className="underline">Create an account</Link></p>
          <p className="mt-4 bg-sand p-3 text-xs text-neutral-600">Demo shopper: maya@ottershops.test / otters-2026</p>
        </>
      ) : (
        <p className="mt-4 text-sm">Already a member? <Link href={`/account/sign-in?next=${encodeURIComponent(next)}`} className="underline">Sign in</Link></p>
      )}
    </div>
  );
}
