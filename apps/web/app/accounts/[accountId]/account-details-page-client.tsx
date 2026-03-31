"use client";

import { OperationalShell } from "../../operational-shell";
import { AccountDetailsModule } from "./account-details-module";

export function AccountDetailsPageClient({
  accountId,
}: {
  accountId: string;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Account ${accountId}`}
      description="Bounded account detail surface showing compact linked subscriber, service-point, and current meter context."
    >
      {({ authorizedFetch }) => (
        <AccountDetailsModule accountId={accountId} authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
