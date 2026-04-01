import { ReadingsPageClient } from "./readings-page-client";

export default async function ReadingsPage({
  searchParams,
}: {
  searchParams: Promise<{ meterId?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const handedOffMeterId = Array.isArray(resolvedSearchParams.meterId)
    ? resolvedSearchParams.meterId[0] ?? null
    : resolvedSearchParams.meterId ?? null;

  return <ReadingsPageClient initialMeterId={handedOffMeterId} />;
}
