import { CommandsPageClient } from "./commands-page-client";

type MeterScopeSource = "visible_filtered_result_set";

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

function resolveMeterScopeSource(
  value: string | string[] | undefined,
): MeterScopeSource | null {
  const resolvedValue = Array.isArray(value) ? value[0] ?? null : value ?? null;
  if (resolvedValue === "visible_filtered_result_set") {
    return resolvedValue;
  }
  return null;
}

export default async function CommandsPage({
  searchParams,
}: {
  searchParams: Promise<{
    meterId?: string | string[];
    meterIds?: string | string[];
    meterScopeSource?: string | string[];
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

  return (
    <CommandsPageClient
      initialMeterIds={initialMeterIds}
      initialMeterScopeSource={initialMeterScopeSource}
    />
  );
}
