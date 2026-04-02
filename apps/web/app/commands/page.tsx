import { CommandsPageClient } from "./commands-page-client";

type MeterScopeSource = "visible_filtered_result_set";
type BulkCommandFamily = "relay_control" | "on_demand_read";
type RecoveryActionSource = "readings_missing_recovery_queue";

type RecoveryActionHandoff = {
  source: RecoveryActionSource;
  issueType: string | null;
  reason: string | null;
  context: string | null;
};

function resolveMeterIds(value: string | string[] | undefined): string[] {
  if (!value) {
    return [];
  }

  const values = Array.isArray(value) ? value : [value];
  return values
    .flatMap((item) => item.split(","))
    .map((item) => item.trim())
    .filter(Boolean);
}

function resolveSingleValue(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0]?.trim() || null;
  }
  return value?.trim() || null;
}

function resolveMeterScopeSource(
  value: string | string[] | undefined,
): MeterScopeSource | null {
  const resolvedValue = resolveSingleValue(value);
  if (resolvedValue === "visible_filtered_result_set") {
    return resolvedValue;
  }
  return null;
}

function resolveInitialCommandFamily(
  value: string | string[] | undefined,
): BulkCommandFamily | null {
  const resolvedValue = resolveSingleValue(value);
  if (resolvedValue === "relay_control" || resolvedValue === "on_demand_read") {
    return resolvedValue;
  }
  return null;
}

function resolveRecoveryActionHandoff(searchParams: {
  recoverySource?: string | string[];
  recoveryIssueType?: string | string[];
  recoveryReason?: string | string[];
  recoveryContext?: string | string[];
}): RecoveryActionHandoff | null {
  const source = resolveSingleValue(searchParams.recoverySource);
  if (source !== "readings_missing_recovery_queue") {
    return null;
  }

  return {
    source,
    issueType: resolveSingleValue(searchParams.recoveryIssueType),
    reason: resolveSingleValue(searchParams.recoveryReason),
    context: resolveSingleValue(searchParams.recoveryContext),
  };
}

export default async function CommandsPage({
  searchParams,
}: {
  searchParams: Promise<{
    meterId?: string | string[];
    meterIds?: string | string[];
    meterScopeSource?: string | string[];
    commandFamily?: string | string[];
    recoverySource?: string | string[];
    recoveryIssueType?: string | string[];
    recoveryReason?: string | string[];
    recoveryContext?: string | string[];
  }>;
}) {
  const resolvedSearchParams = await searchParams;
  const initialMeterIds = Array.from(
    new Set([
      ...resolveMeterIds(resolvedSearchParams.meterId),
      ...resolveMeterIds(resolvedSearchParams.meterIds),
    ]),
  );
  const initialMeterScopeSource = resolveMeterScopeSource(
    resolvedSearchParams.meterScopeSource,
  );
  const initialCommandFamily = resolveInitialCommandFamily(resolvedSearchParams.commandFamily);
  const initialRecoveryAction = resolveRecoveryActionHandoff(resolvedSearchParams);

  return (
    <CommandsPageClient
      initialCommandFamily={initialCommandFamily}
      initialMeterIds={initialMeterIds}
      initialRecoveryAction={initialRecoveryAction}
      initialMeterScopeSource={initialMeterScopeSource}
    />
  );
}
