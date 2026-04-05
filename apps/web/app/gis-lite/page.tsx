import { GisLitePageClient } from "./gis-lite-page-client";

export default async function GisLitePage({
  searchParams,
}: {
  searchParams?: Promise<{ meterId?: string }>;
}) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const initialMeterId = resolvedSearchParams?.meterId?.trim() || null;

  return <GisLitePageClient initialMeterId={initialMeterId} />;
}
