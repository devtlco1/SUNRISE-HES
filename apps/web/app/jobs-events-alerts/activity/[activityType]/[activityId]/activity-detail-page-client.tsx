"use client";

import { OperationalShell } from "../../../../operational-shell";
import { ActivityDetailModule } from "./activity-detail-module";

export function ActivityDetailPageClient({
  activityType,
  activityId,
}: {
  activityType: string;
  activityId: string;
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
        />
      )}
    </OperationalShell>
  );
}
