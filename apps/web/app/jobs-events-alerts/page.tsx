import { JobsEventsAlertsPageClient } from "./jobs-events-alerts-page-client";

function resolveSingleValue(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

type RetryQueueRoundTripContext = {
  source: "activity_detail_roundtrip";
  activityType: "job_run" | "command";
  activityId: string;
} | null;

export default async function JobsEventsAlertsPage({
  searchParams,
}: {
  searchParams?: Promise<{
    attentionContext?: string | string[];
    activityFilter?: string | string[];
    retryQueueReturnSource?: string | string[];
    returnedActivityType?: string | string[];
    returnedActivityId?: string | string[];
  }>;
}) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const attentionContext = resolveSingleValue(resolvedSearchParams?.attentionContext);
  const activityFilter = resolveSingleValue(resolvedSearchParams?.activityFilter);
  const retryQueueReturnSource = resolveSingleValue(resolvedSearchParams?.retryQueueReturnSource);
  const returnedActivityType = resolveSingleValue(resolvedSearchParams?.returnedActivityType);
  const returnedActivityId = resolveSingleValue(resolvedSearchParams?.returnedActivityId);

  const initialAttentionContext =
    attentionContext === "dashboard_attention_queue" && activityFilter === "attention"
      ? {
          source: "dashboard_attention_queue" as const,
          filter: "attention" as const,
        }
      : null;
  const initialRetryQueueRoundTripContext: RetryQueueRoundTripContext =
    retryQueueReturnSource === "activity_detail_roundtrip" &&
    (returnedActivityType === "job_run" || returnedActivityType === "command") &&
    returnedActivityId
      ? {
          source: "activity_detail_roundtrip",
          activityType: returnedActivityType,
          activityId: returnedActivityId,
        }
      : null;

  return (
    <JobsEventsAlertsPageClient
      initialAttentionContext={initialAttentionContext}
      initialRetryQueueRoundTripContext={initialRetryQueueRoundTripContext}
    />
  );
}
