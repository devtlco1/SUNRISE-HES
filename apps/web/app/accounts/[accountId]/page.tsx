import { AccountDetailsPageClient } from "./account-details-page-client";

export default async function AccountDetailsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;

  return <AccountDetailsPageClient accountId={accountId} />;
}
