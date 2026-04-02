import { ActivityDetailPageClient } from "./activity-detail-page-client";

type ActivityDetailReturnContext = {
  source: "commands_remediation";
} | null;

type ActivityDetailEntryContext = {
  source: "jobs_retry_queue";
} | null;

function resolveSingleValue(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function ActivityDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ activityType: string; activityId: string }>;
  searchParams?: Promise<{
    returnSource?: string | string[];
    retryEntrySource?: string | string[];
  }>;
}) {
  const { activityType, activityId } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const returnSource = resolveSingleValue(resolvedSearchParams?.returnSource);
  const retryEntrySource = resolveSingleValue(resolvedSearchParams?.retryEntrySource);
  const initialReturnContext: ActivityDetailReturnContext =
    returnSource === "commands_remediation" ? { source: "commands_remediation" } : null;
  const initialEntryContext: ActivityDetailEntryContext =
    retryEntrySource === "jobs_retry_queue" &&
    (activityType === "job_run" || activityType === "command")
      ? { source: "jobs_retry_queue" }
      : null;

  return (
    <ActivityDetailPageClient
      activityType={activityType}
      activityId={activityId}
      initialEntryContext={initialEntryContext}
      initialReturnContext={initialReturnContext}
    />
  );
}
