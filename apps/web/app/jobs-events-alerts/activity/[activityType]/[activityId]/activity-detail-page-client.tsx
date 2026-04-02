"use client";

import { OperationalShell } from "../../../../operational-shell";
import { ActivityDetailModule } from "./activity-detail-module";

type ActivityDetailReturnContext = {
  source: "commands_remediation";
} | null;

type ActivityDetailEntryContext = {
  source: "jobs_retry_queue";
} | null;

export function ActivityDetailPageClient({
  activityType,
  activityId,
  initialEntryContext = null,
  initialReturnContext = null,
}: {
  activityType: string;
  activityId: string;
  initialEntryContext?: ActivityDetailEntryContext;
  initialReturnContext?: ActivityDetailReturnContext;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title={`Activity ${activityId}`}
      description="Bounded drill-down for one selected monitoring activity item without expanding into a broader incident-management surface."
    >
      {({ authorizedFetch }) => (
        <ActivityDetailModule
          activityType={activityType}
          activityId={activityId}
          authorizedFetch={authorizedFetch}
          initialEntryContext={initialEntryContext}
          initialReturnContext={initialReturnContext}
        />
      )}
    </OperationalShell>
  );
}
