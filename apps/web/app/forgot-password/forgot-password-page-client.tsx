"use client";

import { AuthEntryShell } from "../auth-entry-shell";
import { ForgotPasswordModule } from "./forgot-password-module";

export function ForgotPasswordPageClient() {
  return (
    <AuthEntryShell
      eyebrow="Auth Entry MVP"
      title="Reset access"
      description="Use the bounded password-reset initiation page to recover access to the operational platform."
    >
      <ForgotPasswordModule />
    </AuthEntryShell>
  );
}
