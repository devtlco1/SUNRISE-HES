"use client";

import { OperationalShell } from "../operational-shell";
import { JobsEventsAlertsModule } from "./jobs-events-alerts-module";

type AttentionLandingContext = {
  source: "dashboard_attention_queue";
  filter: "attention";
} | null;

type RetryQueueRoundTripContext = {
  source: "activity_detail_roundtrip";
  activityType: "job_run" | "command";
  activityId: string;
} | null;

export function JobsEventsAlertsPageClient({
  initialAttentionContext = null,
  initialRetryQueueRoundTripContext = null,
}: {
  initialAttentionContext?: AttentionLandingContext;
  initialRetryQueueRoundTripContext?: RetryQueueRoundTripContext;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Jobs / Events / Alerts MVP"
      description="Operational monitoring surface built from the current bounded job, command, and event read APIs."
    >
      {({ authorizedFetch }) => (
        <JobsEventsAlertsModule
          authorizedFetch={authorizedFetch}
          initialAttentionContext={initialAttentionContext}
          initialRetryQueueRoundTripContext={initialRetryQueueRoundTripContext}
        />
      )}
    </OperationalShell>
  );
}
