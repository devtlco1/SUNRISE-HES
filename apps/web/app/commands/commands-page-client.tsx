"use client";

import { CommandsModule } from "./commands-module";
import { OperationalShell } from "../operational-shell";

type RecoveryActionHandoff = {
  source: "readings_missing_recovery_queue";
  issueType: string | null;
  reason: string | null;
  context: string | null;
};

type RetryRemediationHandoff = {
  source: "jobs_retry_queue";
  itemType: "job_run" | "command";
  reason: string | null;
  context: string | null;
};

export function CommandsPageClient({
  initialCommandFamily = null,
  initialMeterIds = [],
  initialRecoveryAction = null,
  initialMeterScopeSource = null,
  initialSelectedCommandId = null,
  initialRetryRemediation = null,
}: {
  initialCommandFamily?: "relay_control" | "on_demand_read" | null;
  initialMeterIds?: string[];
  initialRecoveryAction?: RecoveryActionHandoff | null;
  initialMeterScopeSource?: "visible_filtered_result_set" | null;
  initialSelectedCommandId?: string | null;
  initialRetryRemediation?: RetryRemediationHandoff | null;
}) {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Global Commands MVP"
      description="Operational command visibility over the stable profile capture, relay control, and on-demand read command projections."
    >
      {({ authorizedFetch }) => (
        <CommandsModule
          authorizedFetch={authorizedFetch}
          initialCommandFamily={initialCommandFamily}
          initialMeterIds={initialMeterIds}
          initialRecoveryAction={initialRecoveryAction}
          initialMeterScopeSource={initialMeterScopeSource}
          initialSelectedCommandId={initialSelectedCommandId}
          initialRetryRemediation={initialRetryRemediation}
        />
      )}
    </OperationalShell>
  );
}
