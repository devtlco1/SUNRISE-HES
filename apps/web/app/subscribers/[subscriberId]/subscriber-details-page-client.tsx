"use client";

import { OperationalShell } from "../../operational-shell";
import { SubscriberDetailsModule } from "./subscriber-details-module";

export function SubscriberDetailsPageClient({
  subscriberId,
}: {
  subscriberId: string;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Subscriber ${subscriberId}`}
      description="Bounded subscriber detail surface showing compact account and linked meter visibility without expanding into a full CRM suite."
    >
      {({ authorizedFetch }) => (
        <SubscriberDetailsModule
          subscriberId={subscriberId}
          authorizedFetch={authorizedFetch}
        />
      )}
    </OperationalShell>
  );
}
