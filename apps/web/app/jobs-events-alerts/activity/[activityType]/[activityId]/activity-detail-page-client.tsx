"use client";

import { OperationalShell } from "../../../../operational-shell";
import { ActivityDetailModule } from "./activity-detail-module";

type ActivityDetailReturnContext = {
  source: "commands_remediation";
} | null;

export function ActivityDetailPageClient({
  activityType,
  activityId,
  initialReturnContext = null,
}: {
  activityType: string;
  activityId: string;
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
          initialReturnContext={initialReturnContext}
        />
      )}
    </OperationalShell>
  );
}
