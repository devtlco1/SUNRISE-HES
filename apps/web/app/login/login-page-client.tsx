"use client";

import { useRouter } from "next/navigation";

import { AuthEntryShell } from "../auth-entry-shell";
import { LoginModule } from "./login-module";

export function LoginPageClient() {
  const router = useRouter();

  return (
    <AuthEntryShell
      eyebrow="Auth Entry MVP"
      title="Welcome back"
      description="Sign in to access the existing operational routes through the adopted product shell."
    >
      <LoginModule onLoginSuccess={() => router.push("/")} />
    </AuthEntryShell>
  );
}
