"use client";

import { useRouter } from "next/navigation";

import { AuthEntryShell } from "../auth-entry-shell";
import { LoginModule } from "./login-module";

export function LoginPageClient() {
  const router = useRouter();

  return (
    <AuthEntryShell
      eyebrow="Access"
      title="Sign in"
      description="Use your API base URL and account credentials."
    >
      <LoginModule onLoginSuccess={() => router.push("/")} />
    </AuthEntryShell>
  );
}
