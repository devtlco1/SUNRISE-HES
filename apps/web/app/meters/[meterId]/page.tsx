import { MeterDetailsPageClient } from "./meter-details-page-client";

export default async function MeterDetailsPage({
  params,
  searchParams,
}: {
  params: Promise<{ meterId: string }>;
  searchParams?: Promise<{ tab?: string }>;
}) {
  const { meterId } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const initialTab =
    resolvedSearchParams?.tab === "summary" ||
    resolvedSearchParams?.tab === "attachments" ||
    resolvedSearchParams?.tab === "configuration" ||
    resolvedSearchParams?.tab === "connectivity" ||
    resolvedSearchParams?.tab === "gis" ||
    resolvedSearchParams?.tab === "commercial" ||
    resolvedSearchParams?.tab === "events" ||
    resolvedSearchParams?.tab === "readings" ||
    resolvedSearchParams?.tab === "audit" ||
    resolvedSearchParams?.tab === "commands"
      ? resolvedSearchParams.tab
      : undefined;

  return <MeterDetailsPageClient meterId={meterId} initialTab={initialTab} />;
}
