import { Suspense } from "react";
import { AuthForm } from "@/components/AuthForm";

export const metadata = { title: "Sign in" };
export default function SignInPage() {
  return <Suspense><AuthForm mode="sign-in" /></Suspense>;
}
