import { JobsEventsAlertsPageClient } from "./jobs-events-alerts-page-client";

function resolveSingleValue(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default async function JobsEventsAlertsPage({
  searchParams,
}: {
  searchParams?: Promise<{
    attentionContext?: string | string[];
    activityFilter?: string | string[];
  }>;
}) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const attentionContext = resolveSingleValue(resolvedSearchParams?.attentionContext);
  const activityFilter = resolveSingleValue(resolvedSearchParams?.activityFilter);

  const initialAttentionContext =
    attentionContext === "dashboard_attention_queue" && activityFilter === "attention"
      ? {
          source: "dashboard_attention_queue" as const,
          filter: "attention" as const,
        }
      : null;

  return <JobsEventsAlertsPageClient initialAttentionContext={initialAttentionContext} />;
}
