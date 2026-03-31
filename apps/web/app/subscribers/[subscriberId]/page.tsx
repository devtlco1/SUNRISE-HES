import { SubscriberDetailsPageClient } from "./subscriber-details-page-client";

export default async function SubscriberDetailsPage({
  params,
}: {
  params: Promise<{ subscriberId: string }>;
}) {
  const { subscriberId } = await params;

  return <SubscriberDetailsPageClient subscriberId={subscriberId} />;
}
