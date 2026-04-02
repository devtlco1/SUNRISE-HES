import { ActivityDetailPageClient } from "./activity-detail-page-client";

type ActivityDetailReturnContext = {
  source: "commands_remediation";
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
  searchParams?: Promise<{ returnSource?: string | string[] }>;
}) {
  const { activityType, activityId } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const returnSource = resolveSingleValue(resolvedSearchParams?.returnSource);
  const initialReturnContext: ActivityDetailReturnContext =
    returnSource === "commands_remediation" ? { source: "commands_remediation" } : null;

  return (
    <ActivityDetailPageClient
      activityType={activityType}
      activityId={activityId}
      initialReturnContext={initialReturnContext}
    />
  );
}
