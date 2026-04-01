import { CommandsPageClient } from "./commands-page-client";

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

export default async function CommandsPage({
  searchParams,
}: {
  searchParams: Promise<{ meterId?: string | string[]; meterIds?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const initialMeterIds = Array.from(
    new Set([
      ...resolveMeterIds(resolvedSearchParams.meterId),
      ...resolveMeterIds(resolvedSearchParams.meterIds),
    ]),
  );

  return <CommandsPageClient initialMeterIds={initialMeterIds} />;
}
