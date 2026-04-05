import { MeterDetailClient } from "./meter-detail-client";

export default async function MeterDetailPage({
  params,
}: {
  params: Promise<{ meterId: string }>;
}) {
  const { meterId } = await params;
  return <MeterDetailClient meterId={meterId} />;
}
