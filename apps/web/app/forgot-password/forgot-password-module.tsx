"use client";

import Link from "next/link";
import { useState } from "react";

import { useSession } from "../session-provider";

export function ForgotPasswordModule() {
  const { apiBaseUrl, setApiBaseUrl, requestPasswordReset } = useSession();
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <form
      className="auth-form"
      onSubmit={async (event) => {
        event.preventDefault();
        setFormError(null);
        setFormSuccess(null);
        setIsSubmitting(true);

        try {
          const response = await requestPasswordReset({ usernameOrEmail });
          setFormSuccess(response.message);
        } catch (error) {
          setFormError(
            error instanceof Error
              ? error.message
              : "Unable to start forgot-password flow.",
          );
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <div className="section-heading">
        <div>
          <h2>Forgot password</h2>
          <p className="muted">
            Start the bounded password-reset initiation flow without redesigning
            backend auth behavior.
          </p>
        </div>
      </div>

      <label className="field">
        <span>API base URL</span>
        <input
          value={apiBaseUrl}
          onChange={(event) => setApiBaseUrl(event.target.value)}
          placeholder="http://api.example.com"
        />
      </label>

      <label className="field">
        <span>Username or email</span>
        <input
          value={usernameOrEmail}
          onChange={(event) => setUsernameOrEmail(event.target.value)}
          placeholder="ops@example.com"
        />
      </label>

      <button className="primary-button" disabled={isSubmitting} type="submit">
        {isSubmitting ? "Submitting..." : "Send reset instructions"}
      </button>

      <div className="auth-form-footer">
        <span className="muted">Already have access?</span>
        <Link href="/login">Back to login</Link>
      </div>

      {formSuccess ? <p className="success-banner">{formSuccess}</p> : null}
      {formError ? <p className="error-banner">{formError}</p> : null}
    </form>
  );
}
