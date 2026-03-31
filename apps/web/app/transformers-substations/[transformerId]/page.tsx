import { TransformerSubstationDetailsPageClient } from "./transformer-substation-details-page-client";

export default async function TransformerSubstationDetailsPage({
  params,
}: {
  params: Promise<{ transformerId: string }>;
}) {
  const { transformerId } = await params;
  return <TransformerSubstationDetailsPageClient transformerId={transformerId} />;
}
