import { MeterDetailsCommandsTab } from "./meter-details-commands-tab";

export default async function MeterDetailsPage({
  params,
}: {
  params: Promise<{ meterId: string }>;
}) {
  const { meterId } = await params;

  return <MeterDetailsCommandsTab meterId={meterId} />;
}
