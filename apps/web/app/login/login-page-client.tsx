"use client";

import { useRouter } from "next/navigation";

import { SessionProvider } from "../session-provider";
import { LoginModule } from "./login-module";

export function LoginPageClient() {
  const router = useRouter();

  return (
    <SessionProvider>
      <div className="ws-login">
        <div className="ws-login-panel">
          <h1 className="ws-login-heading">Sign in</h1>
          <p className="ws-muted">API URL and credentials for the existing auth flow.</p>
          <LoginModule onLoginSuccess={() => router.push("/")} />
        </div>
      </div>
    </SessionProvider>
  );
}
