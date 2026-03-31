import { MeterDetailsPageClient } from "./meter-details-page-client";

export default async function MeterDetailsPage({
  params,
}: {
  params: Promise<{ meterId: string }>;
}) {
  const { meterId } = await params;

  return <MeterDetailsPageClient meterId={meterId} />;
}
