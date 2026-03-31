import { ActivityDetailPageClient } from "./activity-detail-page-client";

export default async function ActivityDetailPage({
  params,
}: {
  params: Promise<{ activityType: string; activityId: string }>;
}) {
  const { activityType, activityId } = await params;

  return (
    <ActivityDetailPageClient
      activityType={activityType}
      activityId={activityId}
    />
  );
}
