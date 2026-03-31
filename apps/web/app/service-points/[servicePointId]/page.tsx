import { ServicePointDetailsPageClient } from "./service-point-details-page-client";

export default async function ServicePointDetailsPage({
  params,
}: {
  params: Promise<{ servicePointId: string }>;
}) {
  const { servicePointId } = await params;

  return <ServicePointDetailsPageClient servicePointId={servicePointId} />;
}
