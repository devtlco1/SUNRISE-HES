"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type CommandOperationalFamily =
  | "profile_capture"
  | "relay_control"
  | "on_demand_read";
type FamilyFilter = "all" | CommandOperationalFamily;
type BulkCommandFamily = "relay_control" | "on_demand_read";
type ApprovalFamilyFilter = "all" | BulkCommandFamily;
type ApprovalHistoryFilter = "all_decisions" | "approved" | "rejected";
type RelayOperation = "disconnect" | "reconnect";
type OnDemandReadOperation = "read_billing_snapshot";

type CommandRecentItem = {
  command_id: string;
  command_family: CommandOperationalFamily;
  command_category: string;
  command_status: string;
  approval_status: string;
  approval_reviewed_at: string | null;
  approval_notes: string | null;
  meter_id: string;
  command_template_code: string;
  latest_command_execution_attempt_id: string | null;
  latest_command_execution_attempt_status: string | null;
  runtime_execution_record_id: string | null;
  family_specific_outcome_summary: Record<string, string | null>;
  orchestration_artifact_present: boolean;
  terminalization_artifact_present: boolean;
  execute_now_artifact_present: boolean;
  created_at: string;
  latest_updated_at: string;
};

type CommandRecentListResponse = {
  total: number;
  limit: number;
  family_filter: CommandOperationalFamily | null;
  approval_filter?: string | null;
  items: CommandRecentItem[];
};

type CommandDetail = {
  command_id: string;
  command_family: CommandOperationalFamily;
  command_category: string;
  command_status: string;
  approval_status: string;
  approval_reviewed_at: string | null;
  approval_reviewed_by_user_id: string | null;
  approval_notes: string | null;
  meter_id: string;
  command_template_code: string;
  latest_command_execution_attempt_id: string | null;
  latest_command_execution_attempt_status: string | null;
  runtime_execution_record_id: string | null;
  family_specific_outcome_summary: Record<string, string | null>;
  orchestration_artifact_present: boolean;
  terminalization_artifact_present: boolean;
  execute_now_artifact_present: boolean;
  created_at: string;
  latest_updated_at: string;
  projection_record: Record<string, unknown>;
};

type CommandDetailResponse = {
  result: CommandDetail;
};

type MeterItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  current_status: string;
  last_seen_at: string | null;
};

type MeterListResponse = {
  total: number;
  items: MeterItem[];
};

type CommandTemplate = {
  id: string;
  code: string;
  name: string;
  category: string;
  is_active: boolean;
};

type CommandTemplateListResponse = {
  total: number;
  items: CommandTemplate[];
};

type BulkCommandResultItem = {
  meter_id: string;
  command_id: string | null;
  command_template_code: string | null;
  command_family: BulkCommandFamily;
  command_status: string | null;
  approval_status: string | null;
  submission_status: string;
  detail: string | null;
};

type BulkCommandResponse = {
  submitted_total: number;
  failed_total: number;
  items: BulkCommandResultItem[];
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatFamilySummary(item: Record<string, string | null>): string {
  if ("terminal_status_category" in item) {
    return item.terminal_status_category ?? "No terminal status yet";
  }
  if ("relay_control_operation" in item) {
    const operation = item.relay_control_operation ?? "relay";
    const outcome = item.relay_control_execution_outcome ?? "pending";
    return `${operation} (${outcome})`;
  }
  if ("on_demand_read_operation" in item) {
    const operation = item.on_demand_read_operation ?? "read";
    const snapshotType = item.snapshot_type ?? "snapshot";
    const outcome = item.on_demand_read_execution_outcome ?? "pending";
    return `${operation} ${snapshotType} (${outcome})`;
  }
  return "No operational summary yet";
}

function formatCommandFamilyLabel(value: CommandOperationalFamily): string {
  switch (value) {
    case "profile_capture":
      return "Profile capture";
    case "relay_control":
      return "Relay control";
    case "on_demand_read":
      return "On-demand read";
  }
}

function formatCommandCategoryLabel(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatStatusLabel(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("succeed") ||
    normalized.includes("complete") ||
    normalized.includes("acknowledged") ||
    normalized.includes("active")
  ) {
    return "positive";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("cancel") ||
    normalized.includes("reject")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("queued") ||
    normalized.includes("running") ||
    normalized.includes("progress")
  ) {
    return "warning";
  }
  return "neutral";
}

function formatProjectionKey(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function sortRecentCommandsByUpdatedAt(items: CommandRecentItem[]): CommandRecentItem[] {
  return [...items].sort(
    (left, right) =>
      new Date(right.approval_reviewed_at ?? right.latest_updated_at).getTime() -
      new Date(left.approval_reviewed_at ?? left.latest_updated_at).getTime(),
  );
}

function matchesApprovalSearch(command: CommandRecentItem, query: string): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  return [
    command.command_template_code,
    command.meter_id,
    command.command_category,
    command.command_family,
    command.command_status,
    command.approval_status,
    command.approval_notes,
    formatFamilySummary(command.family_specific_outcome_summary),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalizedQuery));
}

function haveSameMeterIds(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  const leftSet = new Set(left);
  return right.every((meterId) => leftSet.has(meterId));
}

export function CommandsModule({
  authorizedFetch,
  initialMeterIds = [],
  initialMeterScopeSource = null,
}: {
  authorizedFetch: AuthorizedFetch;
  initialMeterIds?: string[];
  initialMeterScopeSource?: "visible_filtered_result_set" | null;
}) {
  const [recentFamilyFilter, setRecentFamilyFilter] = useState<FamilyFilter>("all");
  const [recentCommands, setRecentCommands] = useState<CommandRecentItem[]>([]);
  const [availableMeters, setAvailableMeters] = useState<MeterItem[]>([]);
  const [availableTemplates, setAvailableTemplates] = useState<CommandTemplate[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<CommandRecentItem[]>([]);
  const [approvalHistoryItems, setApprovalHistoryItems] = useState<CommandRecentItem[]>([]);
  const [selectedCommandId, setSelectedCommandId] = useState<string | null>(null);
  const [selectedCommandDetail, setSelectedCommandDetail] =
    useState<CommandDetail | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [wizardContextError, setWizardContextError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [bulkActionError, setBulkActionError] = useState<string | null>(null);
  const [bulkActionSuccess, setBulkActionSuccess] = useState<string | null>(null);
  const [bulkSubmissionResult, setBulkSubmissionResult] = useState<BulkCommandResponse | null>(
    null,
  );
  const [approvalActionError, setApprovalActionError] = useState<string | null>(null);
  const [approvalActionSuccess, setApprovalActionSuccess] = useState<string | null>(null);
  const [isLoadingRecentCommands, setIsLoadingRecentCommands] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isLoadingWizardContext, setIsLoadingWizardContext] = useState(false);
  const [isLoadingPendingApprovals, setIsLoadingPendingApprovals] = useState(false);
  const [isLoadingApprovalHistory, setIsLoadingApprovalHistory] = useState(false);
  const [isSubmittingBulkRequest, setIsSubmittingBulkRequest] = useState(false);
  const [activeApprovalActionCommandId, setActiveApprovalActionCommandId] = useState<
    string | null
  >(null);
  const [wizardFamily, setWizardFamily] = useState<BulkCommandFamily>("relay_control");
  const [wizardRelayOperation, setWizardRelayOperation] = useState<RelayOperation>("disconnect");
  const [wizardOnDemandReadOperation] =
    useState<OnDemandReadOperation>("read_billing_snapshot");
  const [wizardTemplateId, setWizardTemplateId] = useState("");
  const [wizardMeterSearchQuery, setWizardMeterSearchQuery] = useState("");
  const [selectedWizardMeterIds, setSelectedWizardMeterIds] = useState<string[]>([]);
  const [isSelectFilteredConfirmationVisible, setIsSelectFilteredConfirmationVisible] =
    useState(false);
  const [bulkNotes, setBulkNotes] = useState("");
  const [approvalFamilyFilter, setApprovalFamilyFilter] =
    useState<ApprovalFamilyFilter>("all");
  const [approvalHistoryFilter, setApprovalHistoryFilter] =
    useState<ApprovalHistoryFilter>("all_decisions");
  const [approvalSearchQuery, setApprovalSearchQuery] = useState("");
  const hasAppliedInitialTargetScopeRef = useRef(false);
  const handedOffMeterIds = useMemo(
    () =>
      Array.from(
        new Set(
          initialMeterIds
            .map((meterId) => meterId.trim())
            .filter(Boolean),
        ),
      ),
    [initialMeterIds],
  );

  const loadRecentCommands = useCallback(
    async (preferredCommandId?: string) => {
      setIsLoadingRecentCommands(true);
      setPageError(null);

      try {
        const familyQuery =
          recentFamilyFilter === "all" ? "" : `&family=${recentFamilyFilter}`;
        const response = await authorizedFetch<CommandRecentListResponse>(
          `/api/v1/commands/recent?limit=20${familyQuery}`,
        );
        setRecentCommands(response.items);
        setSelectedCommandId((currentSelectedCommandId) => {
          if (
            preferredCommandId &&
            response.items.some((item) => item.command_id === preferredCommandId)
          ) {
            return preferredCommandId;
          }
          if (
            currentSelectedCommandId &&
            response.items.some((item) => item.command_id === currentSelectedCommandId)
          ) {
            return currentSelectedCommandId;
          }
          return response.items[0]?.command_id ?? null;
        });
      } catch (error) {
        setPageError(
          error instanceof Error ? error.message : "Unable to load recent commands.",
        );
      } finally {
        setIsLoadingRecentCommands(false);
      }
    },
    [authorizedFetch, recentFamilyFilter],
  );

  const loadWizardContext = useCallback(async () => {
    setIsLoadingWizardContext(true);
    setWizardContextError(null);

    try {
      const [metersResponse, templatesResponse] = await Promise.all([
        authorizedFetch<MeterListResponse>("/api/v1/meters?offset=0&limit=20"),
        authorizedFetch<CommandTemplateListResponse>("/api/v1/command-templates"),
      ]);
      setAvailableMeters(metersResponse.items);
      setAvailableTemplates(templatesResponse.items);
    } catch (error) {
      setAvailableMeters([]);
      setAvailableTemplates([]);
      setWizardContextError(
        error instanceof Error ? error.message : "Unable to load bulk command wizard context.",
      );
    } finally {
      setIsLoadingWizardContext(false);
    }
  }, [authorizedFetch]);

  const loadPendingApprovals = useCallback(async () => {
    setIsLoadingPendingApprovals(true);
    setApprovalActionError(null);

    try {
      const familyQuery =
        approvalFamilyFilter === "all" ? "" : `&family=${approvalFamilyFilter}`;
      const response = await authorizedFetch<CommandRecentListResponse>(
        `/api/v1/commands/approvals/pending?limit=20${familyQuery}`,
      );
      setPendingApprovals(response.items);
    } catch (error) {
      setPendingApprovals([]);
      setApprovalActionError(
        error instanceof Error ? error.message : "Unable to load pending approvals.",
      );
    } finally {
      setIsLoadingPendingApprovals(false);
    }
  }, [approvalFamilyFilter, authorizedFetch]);

  const loadApprovalHistory = useCallback(async () => {
    setIsLoadingApprovalHistory(true);

    try {
      const familyQuery =
        approvalFamilyFilter === "all" ? "" : `&family=${approvalFamilyFilter}`;

      if (approvalHistoryFilter === "approved" || approvalHistoryFilter === "rejected") {
        const response = await authorizedFetch<CommandRecentListResponse>(
          `/api/v1/commands/recent?limit=20${familyQuery}&approval=${approvalHistoryFilter}`,
        );
        setApprovalHistoryItems(sortRecentCommandsByUpdatedAt(response.items));
        return;
      }

      const [approvedResponse, rejectedResponse] = await Promise.all([
        authorizedFetch<CommandRecentListResponse>(
          `/api/v1/commands/recent?limit=20${familyQuery}&approval=approved`,
        ),
        authorizedFetch<CommandRecentListResponse>(
          `/api/v1/commands/recent?limit=20${familyQuery}&approval=rejected`,
        ),
      ]);
      setApprovalHistoryItems(
        sortRecentCommandsByUpdatedAt([...approvedResponse.items, ...rejectedResponse.items]).slice(
          0,
          20,
        ),
      );
    } catch (error) {
      setApprovalHistoryItems([]);
      setApprovalActionError(
        error instanceof Error ? error.message : "Unable to load recent approval history.",
      );
    } finally {
      setIsLoadingApprovalHistory(false);
    }
  }, [approvalFamilyFilter, approvalHistoryFilter, authorizedFetch]);

  const loadCommandDetail = useCallback(
    async (commandId: string) => {
      setIsLoadingDetail(true);
      setDetailError(null);

      try {
        const response = await authorizedFetch<CommandDetailResponse>(
          `/api/v1/commands/${commandId}/detail`,
        );
        setSelectedCommandDetail(response.result);
      } catch (error) {
        setSelectedCommandDetail(null);
        setDetailError(
          error instanceof Error ? error.message : "Unable to load command detail.",
        );
      } finally {
        setIsLoadingDetail(false);
      }
    },
    [authorizedFetch],
  );

  useEffect(() => {
    void loadRecentCommands();
  }, [loadRecentCommands]);

  useEffect(() => {
    void loadWizardContext();
  }, [loadWizardContext]);

  useEffect(() => {
    void loadPendingApprovals();
  }, [loadPendingApprovals]);

  useEffect(() => {
    void loadApprovalHistory();
  }, [loadApprovalHistory]);

  useEffect(() => {
    if (!selectedCommandId) {
      setSelectedCommandDetail(null);
      setDetailError(null);
      return;
    }
    void loadCommandDetail(selectedCommandId);
  }, [loadCommandDetail, selectedCommandId]);

  const selectedRecentCommand = useMemo(
    () =>
      recentCommands.find((command) => command.command_id === selectedCommandId) ??
      recentCommands[0] ??
      null,
    [recentCommands, selectedCommandId],
  );

  const wizardTemplates = useMemo(() => {
    const activeTemplates = availableTemplates.filter((template) => template.is_active);
    if (wizardFamily === "relay_control") {
      const expectedCategory =
        wizardRelayOperation === "disconnect" ? "remote_disconnect" : "remote_reconnect";
      return activeTemplates.filter((template) => template.category === expectedCategory);
    }
    return activeTemplates.filter((template) => template.category === "on_demand_read");
  }, [availableTemplates, wizardFamily, wizardRelayOperation]);

  const filteredWizardMeters = useMemo(() => {
    const normalizedQuery = wizardMeterSearchQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return availableMeters;
    }

    return availableMeters.filter((meter) =>
      [
        meter.serial_number,
        meter.utility_meter_number,
        meter.communication_profile_code,
        meter.meter_profile_code,
        meter.id,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
    );
  }, [availableMeters, wizardMeterSearchQuery]);
  const filteredWizardMeterIds = useMemo(
    () => filteredWizardMeters.map((meter) => meter.id),
    [filteredWizardMeters],
  );

  const selectedWizardMeters = useMemo(() => {
    const metersById = new Map(availableMeters.map((meter) => [meter.id, meter]));
    return selectedWizardMeterIds
      .map((meterId) => metersById.get(meterId) ?? null)
      .filter((meter): meter is MeterItem => meter !== null);
  }, [availableMeters, selectedWizardMeterIds]);

  const handedOffWizardMeters = useMemo(() => {
    const metersById = new Map(availableMeters.map((meter) => [meter.id, meter]));
    return handedOffMeterIds
      .map((meterId) => metersById.get(meterId) ?? null)
      .filter((meter): meter is MeterItem => meter !== null);
  }, [availableMeters, handedOffMeterIds]);

  const unresolvedHandedOffMeterIds = useMemo(
    () =>
      handedOffMeterIds.filter(
        (meterId) => !availableMeters.some((meter) => meter.id === meterId),
      ),
    [availableMeters, handedOffMeterIds],
  );
  const handedOffMeterIdSet = useMemo(() => new Set(handedOffMeterIds), [handedOffMeterIds]);
  const selectedHandedOffWizardMeters = useMemo(
    () => selectedWizardMeters.filter((meter) => handedOffMeterIdSet.has(meter.id)),
    [handedOffMeterIdSet, selectedWizardMeters],
  );
  const selectedManualWizardMeters = useMemo(
    () => selectedWizardMeters.filter((meter) => !handedOffMeterIdSet.has(meter.id)),
    [handedOffMeterIdSet, selectedWizardMeters],
  );

  const handedOffScopeSummary = useMemo(() => {
    if (handedOffMeterIds.length === 0) {
      return null;
    }

    if (initialMeterScopeSource === "visible_filtered_result_set") {
      return `${handedOffMeterIds.length} handed-off target${handedOffMeterIds.length === 1 ? "" : "s"} arrived from the visible filtered meter result set. Review the scope below before continuing with the bulk wizard.`;
    }

    return `${handedOffMeterIds.length} handed-off target${handedOffMeterIds.length === 1 ? "" : "s"} arrived in the bulk wizard. Review the scope below before continuing.`;
  }, [handedOffMeterIds, initialMeterScopeSource]);
  const shouldConfirmSelectFilteredReplacement = useMemo(
    () =>
      selectedWizardMeterIds.length > 0 &&
      !haveSameMeterIds(selectedWizardMeterIds, filteredWizardMeterIds),
    [filteredWizardMeterIds, selectedWizardMeterIds],
  );
  const selectFilteredConfirmationSummary = useMemo(() => {
    if (!shouldConfirmSelectFilteredReplacement) {
      return null;
    }

    return `Select filtered will replace the current ${selectedWizardMeterIds.length} selected target${selectedWizardMeterIds.length === 1 ? "" : "s"} with the ${filteredWizardMeterIds.length} meter${filteredWizardMeterIds.length === 1 ? "" : "s"} currently visible in the target filter. Click Confirm replace with filtered to continue.`;
  }, [
    filteredWizardMeterIds.length,
    selectedWizardMeterIds.length,
    shouldConfirmSelectFilteredReplacement,
  ]);

  useEffect(() => {
    if (!wizardTemplates.some((template) => template.id === wizardTemplateId)) {
      setWizardTemplateId(wizardTemplates[0]?.id ?? "");
    }
  }, [wizardTemplateId, wizardTemplates]);

  useEffect(() => {
    if (hasAppliedInitialTargetScopeRef.current) {
      return;
    }
    if (isLoadingWizardContext) {
      return;
    }
    if (availableMeters.length === 0 && wizardContextError === null) {
      return;
    }
    if (handedOffMeterIds.length === 0) {
      hasAppliedInitialTargetScopeRef.current = true;
      return;
    }

    const availableMeterIds = new Set(availableMeters.map((meter) => meter.id));
    const matchedHandedOffMeterIds = handedOffMeterIds.filter((meterId) =>
      availableMeterIds.has(meterId),
    );
    setSelectedWizardMeterIds((currentSelectedMeterIds) =>
      currentSelectedMeterIds.length > 0
        ? currentSelectedMeterIds
        : matchedHandedOffMeterIds,
    );
    hasAppliedInitialTargetScopeRef.current = true;
  }, [availableMeters, handedOffMeterIds, isLoadingWizardContext, wizardContextError]);

  useEffect(() => {
    setIsSelectFilteredConfirmationVisible(false);
  }, [filteredWizardMeterIds, selectedWizardMeterIds, wizardMeterSearchQuery]);

  const filteredPendingApprovals = useMemo(
    () =>
      pendingApprovals.filter((command) => matchesApprovalSearch(command, approvalSearchQuery)),
    [approvalSearchQuery, pendingApprovals],
  );

  const filteredApprovalHistoryItems = useMemo(
    () =>
      approvalHistoryItems.filter((command) => matchesApprovalSearch(command, approvalSearchQuery)),
    [approvalHistoryItems, approvalSearchQuery],
  );

  const overviewCards = useMemo(
    () => [
      {
        label: "Commands in current result set",
        value: String(recentCommands.length),
        note:
          recentFamilyFilter === "all"
            ? "All stable command families"
            : `${formatCommandFamilyLabel(recentFamilyFilter)} only`,
      },
      {
        label: "Families represented",
        value: String(new Set(recentCommands.map((item) => item.command_family)).size),
        note: "Profile capture, relay control, on-demand read",
      },
      {
        label: "Commands with runtime records",
        value: String(
          recentCommands.filter((item) => item.runtime_execution_record_id !== null).length,
        ),
        note: "Visible from the current command projection",
      },
      {
        label: "Selected command status",
        value: selectedRecentCommand
          ? formatStatusLabel(selectedRecentCommand.command_status)
          : "No selection",
        note: selectedRecentCommand
          ? formatFamilySummary(selectedRecentCommand.family_specific_outcome_summary)
          : "Choose a command to inspect bounded detail",
      },
      {
        label: "Pending approvals",
        value: String(pendingApprovals.length),
        note:
          pendingApprovals.length > 0
            ? "Bulk-requested commands currently waiting for review"
            : "No commands are waiting for approval",
      },
      {
        label: "Recent approval decisions",
        value: String(approvalHistoryItems.length),
        note:
          approvalHistoryItems.length > 0
            ? "Approved and rejected outcomes visible from the bounded command projection"
            : "No recent approval decisions are currently visible",
      },
    ],
    [
      approvalHistoryItems.length,
      pendingApprovals.length,
      recentCommands,
      recentFamilyFilter,
      selectedRecentCommand,
    ],
  );

  const toggleWizardMeterSelection = useCallback((meterId: string) => {
    setSelectedWizardMeterIds((current) =>
      current.includes(meterId)
        ? current.filter((item) => item !== meterId)
        : [...current, meterId],
    );
  }, []);

  const selectAllFilteredWizardMeters = useCallback(() => {
    if (shouldConfirmSelectFilteredReplacement && !isSelectFilteredConfirmationVisible) {
      setIsSelectFilteredConfirmationVisible(true);
      return;
    }

    setSelectedWizardMeterIds(filteredWizardMeterIds);
    setIsSelectFilteredConfirmationVisible(false);
  }, [
    filteredWizardMeterIds,
    isSelectFilteredConfirmationVisible,
    shouldConfirmSelectFilteredReplacement,
  ]);

  const restoreHandedOffWizardMeters = useCallback(() => {
    setSelectedWizardMeterIds(handedOffWizardMeters.map((meter) => meter.id));
  }, [handedOffWizardMeters]);

  const handleBulkSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setIsSubmittingBulkRequest(true);
      setBulkActionError(null);
      setBulkActionSuccess(null);
      setBulkSubmissionResult(null);

      try {
        const response = await authorizedFetch<BulkCommandResponse>("/api/v1/commands/bulk-requests", {
          method: "POST",
          body: JSON.stringify({
            family: wizardFamily,
            meter_ids: selectedWizardMeterIds,
            command_template_id: wizardTemplateId,
            relay_operation: wizardFamily === "relay_control" ? wizardRelayOperation : undefined,
            on_demand_read_operation:
              wizardFamily === "on_demand_read" ? wizardOnDemandReadOperation : undefined,
            notes: bulkNotes.trim() || undefined,
          }),
        });

        setBulkSubmissionResult(response);
        setBulkActionSuccess(
          response.failed_total > 0
            ? `${response.submitted_total} bulk command requests submitted for approval. ${response.failed_total} targets need operator follow-up.`
            : `${response.submitted_total} bulk command requests submitted for approval.`,
        );
        const firstSubmittedCommand = response.items.find((item) => item.command_id)?.command_id;
        await Promise.all([
          loadRecentCommands(firstSubmittedCommand ?? undefined),
          loadPendingApprovals(),
          loadApprovalHistory(),
        ]);
      } catch (error) {
        setBulkActionError(
          error instanceof Error ? error.message : "Unable to submit bulk commands for approval.",
        );
      } finally {
        setIsSubmittingBulkRequest(false);
      }
    },
    [
      authorizedFetch,
      bulkNotes,
      loadApprovalHistory,
      loadPendingApprovals,
      loadRecentCommands,
      selectedWizardMeterIds,
      wizardFamily,
      wizardOnDemandReadOperation,
      wizardRelayOperation,
      wizardTemplateId,
    ],
  );

  const handleApprovalAction = useCallback(
    async (commandId: string, action: "approve" | "reject") => {
      setActiveApprovalActionCommandId(commandId);
      setApprovalActionError(null);
      setApprovalActionSuccess(null);

      try {
        await authorizedFetch(`/api/v1/commands/${commandId}/approvals/${action}`, {
          method: "POST",
          body: JSON.stringify({
            approval_notes:
              action === "approve"
                ? "Approved from the bounded bulk approvals MVP."
                : "Rejected from the bounded bulk approvals MVP.",
          }),
        });

        await Promise.all([
          loadPendingApprovals(),
          loadApprovalHistory(),
          loadRecentCommands(commandId),
        ]);
        await loadCommandDetail(commandId);
        setSelectedCommandId(commandId);
        setApprovalActionSuccess(
          action === "approve"
            ? "Selected command approval accepted."
            : "Selected command approval rejected.",
        );
      } catch (error) {
        setApprovalActionError(
          error instanceof Error ? error.message : "Unable to update command approval.",
        );
      } finally {
        setActiveApprovalActionCommandId(null);
      }
    },
    [
      authorizedFetch,
      loadApprovalHistory,
      loadCommandDetail,
      loadPendingApprovals,
      loadRecentCommands,
    ],
  );

  const projectionEntries = useMemo(
    () =>
      selectedCommandDetail
        ? Object.entries(selectedCommandDetail.family_specific_outcome_summary).filter(
            ([, value]) => value !== null,
          )
        : [],
    [selectedCommandDetail],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel commands-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Commands command center</h2>
              <p className="muted">
                Operational command visibility aligned with the adopted shell while
                staying bounded to the stable command families and current read models.
              </p>
            </div>
            <span className="artifact-pill">
              {recentFamilyFilter === "all"
                ? "All supported families"
                : `${formatCommandFamilyLabel(recentFamilyFilter)} filter`}
            </span>
          </div>

          <div className="commands-overview-grid">
            {overviewCards.map((card) => (
              <div key={card.label} className="stat-card commands-overview-card">
                <span className="stat-label">{card.label}</span>
                <strong>{card.value}</strong>
                <p className="muted">{card.note}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="commands-phase-two-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Bulk command wizard</h2>
                <p className="muted">
                  Bounded Phase 2 request flow for relay control and on-demand read,
                  starting with manual multi-select and approval routing only.
                </p>
              </div>
              <span className="artifact-pill">Submits for approval</span>
            </div>

            {wizardContextError ? <p className="error-banner">{wizardContextError}</p> : null}
            {bulkActionError ? <p className="error-banner">{bulkActionError}</p> : null}
            {bulkActionSuccess ? <p className="success-banner">{bulkActionSuccess}</p> : null}

            {isLoadingWizardContext ? (
              <p className="muted">Loading bulk command wizard context...</p>
            ) : (
              <form className="detail-stack" onSubmit={handleBulkSubmit}>
                <div className="inline-form">
                  <label className="field">
                    <span>Command family</span>
                    <select
                      onChange={(event) =>
                        setWizardFamily(event.target.value as BulkCommandFamily)
                      }
                      value={wizardFamily}
                    >
                      <option value="relay_control">Relay control</option>
                      <option value="on_demand_read">On-demand read</option>
                    </select>
                  </label>

                  {wizardFamily === "relay_control" ? (
                    <label className="field">
                      <span>Relay operation</span>
                      <select
                        onChange={(event) =>
                          setWizardRelayOperation(event.target.value as RelayOperation)
                        }
                        value={wizardRelayOperation}
                      >
                        <option value="disconnect">Disconnect</option>
                        <option value="reconnect">Reconnect</option>
                      </select>
                    </label>
                  ) : null}

                  <label className="field">
                    <span>Command template</span>
                    <select
                      onChange={(event) => setWizardTemplateId(event.target.value)}
                      value={wizardTemplateId}
                    >
                      {wizardTemplates.length === 0 ? (
                        <option value="">No compatible template</option>
                      ) : null}
                      {wizardTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.code}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="inline-form">
                  <label className="field">
                    <span>Bulk notes</span>
                    <textarea
                      onChange={(event) => setBulkNotes(event.target.value)}
                      placeholder="Optional operator context for the bounded approvals queue"
                      rows={3}
                      value={bulkNotes}
                    />
                  </label>
                </div>

                <div className="commands-selection-summary">
                  <span className="artifact-pill">
                    {selectedWizardMeterIds.length} target
                    {selectedWizardMeterIds.length === 1 ? "" : "s"} selected
                  </span>
                  <span className="artifact-pill">
                    {filteredWizardMeters.length} meter
                    {filteredWizardMeters.length === 1 ? "" : "s"} in current target filter
                  </span>
                  <span className="artifact-pill">
                    {wizardFamily === "relay_control"
                      ? `${formatCommandFamilyLabel(wizardFamily)} ${formatStatusLabel(
                          wizardRelayOperation,
                        )}`
                      : "On-demand read billing snapshot"}
                  </span>
                </div>

                {handedOffMeterIds.length > 0 ? (
                  <div className="detail-stack">
                    {handedOffScopeSummary ? (
                      <p className="muted">{handedOffScopeSummary}</p>
                    ) : null}
                    <div className="artifact-row">
                    <span className="artifact-pill">
                      {handedOffWizardMeters.length} handed-off target
                      {handedOffWizardMeters.length === 1 ? "" : "s"} loaded
                    </span>
                    {unresolvedHandedOffMeterIds.length > 0 ? (
                      <span className="artifact-pill">
                        {unresolvedHandedOffMeterIds.length} handoff target
                        {unresolvedHandedOffMeterIds.length === 1 ? "" : "s"} outside the
                        current wizard context
                      </span>
                    ) : null}
                    <span className="muted">
                      Meter-context handoff is preserved until you change the target scope.
                    </span>
                    </div>
                  </div>
                ) : null}

                <div className="detail-stack">
                  <div className="section-heading">
                    <div>
                      <h3>Selected target review</h3>
                      <p className="muted">
                        Confirm the current bulk target scope and remove any meter before
                        submitting for approval.
                      </p>
                    </div>
                    <span className="artifact-pill">
                      {selectedWizardMeters.length} included meter
                      {selectedWizardMeters.length === 1 ? "" : "s"}
                    </span>
                  </div>

                  {selectedWizardMeters.length > 0 ? (
                    <div className="artifact-row">
                      <span className="artifact-pill">
                        {selectedHandedOffWizardMeters.length} handed-off target
                        {selectedHandedOffWizardMeters.length === 1 ? "" : "s"}
                      </span>
                      <span className="artifact-pill">
                        {selectedManualWizardMeters.length} manually added target
                        {selectedManualWizardMeters.length === 1 ? "" : "s"}
                      </span>
                      {selectedHandedOffWizardMeters.length > 0 &&
                      selectedManualWizardMeters.length > 0 ? (
                        <span className="muted">
                          Handed-off and manually added targets are both included in the
                          current review scope.
                        </span>
                      ) : null}
                    </div>
                  ) : null}

                  {selectedWizardMeters.length === 0 ? (
                    <p className="muted">
                      No targets selected yet. Choose meters below
                      {handedOffMeterIds.length > 0
                        ? " or restore the handed-off scope."
                        : "."}
                    </p>
                  ) : (
                    <div className="command-list">
                      {selectedWizardMeters.map((meter) => (
                        <article key={meter.id} className="command-list-item">
                          <div className="command-list-item-header">
                            <strong>{meter.serial_number}</strong>
                            <div className="artifact-row">
                              <span className="artifact-pill">
                                {handedOffMeterIdSet.has(meter.id)
                                  ? "Handed-off target"
                                  : "Manually added target"}
                              </span>
                              <span className={`status-pill ${buildStatusTone(meter.current_status)}`}>
                                {formatStatusLabel(meter.current_status)}
                              </span>
                            </div>
                          </div>
                          <div className="command-list-item-meta">
                            <span>Meter {meter.id}</span>
                            <span>
                              {meter.utility_meter_number ?? "No utility meter number"}
                            </span>
                          </div>
                          <div className="command-list-item-meta">
                            <span>
                              {meter.communication_profile_code ??
                                meter.meter_profile_code ??
                                "No profile summary"}
                            </span>
                            <span>Last seen {formatDateTime(meter.last_seen_at)}</span>
                          </div>
                          <div className="artifact-row">
                            <button
                              className="secondary-button"
                              onClick={() => toggleWizardMeterSelection(meter.id)}
                              type="button"
                            >
                              Remove {meter.serial_number}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>

                <div className="inline-form">
                  <label className="field">
                    <span>Target filter</span>
                    <input
                      aria-label="Bulk target filter"
                      onChange={(event) => setWizardMeterSearchQuery(event.target.value)}
                      placeholder="Search serial number, utility number, profile, or meter ID"
                      type="search"
                      value={wizardMeterSearchQuery}
                    />
                  </label>
                </div>

                <div className="artifact-row">
                  <button
                    className="secondary-button"
                    onClick={selectAllFilteredWizardMeters}
                    type="button"
                  >
                    {isSelectFilteredConfirmationVisible && shouldConfirmSelectFilteredReplacement
                      ? "Confirm replace with filtered"
                      : "Select filtered"}
                  </button>
                  <button
                    className="secondary-button"
                    onClick={() => setSelectedWizardMeterIds([])}
                    type="button"
                  >
                    Clear selection
                  </button>
                  {handedOffMeterIds.length > 0 ? (
                    <button
                      className="secondary-button"
                      onClick={restoreHandedOffWizardMeters}
                      type="button"
                    >
                      Restore handed-off targets
                    </button>
                  ) : null}
                  <button
                    className="primary-button"
                    disabled={
                      isSubmittingBulkRequest ||
                      selectedWizardMeterIds.length === 0 ||
                      wizardTemplateId === ""
                    }
                    type="submit"
                  >
                    {isSubmittingBulkRequest ? "Submitting..." : "Submit for approval"}
                  </button>
                </div>

                {isSelectFilteredConfirmationVisible && selectFilteredConfirmationSummary ? (
                  <p className="muted">{selectFilteredConfirmationSummary}</p>
                ) : null}

                <p className="muted">
                  Select filtered replaces the current selected target set with the{" "}
                  {filteredWizardMeters.length} meter
                  {filteredWizardMeters.length === 1 ? "" : "s"} currently visible in the
                  target filter.
                </p>

                <div className="command-list">
                  {filteredWizardMeters.length === 0 ? (
                    <p className="muted">
                      No meters match the current bulk target filter.
                    </p>
                  ) : null}

                  {filteredWizardMeters.map((meter) => {
                    const isSelected = selectedWizardMeterIds.includes(meter.id);
                    return (
                      <article
                        key={meter.id}
                        className={isSelected ? "command-list-item selected" : "command-list-item"}
                      >
                        <div className="command-list-item-header">
                          <strong>{meter.serial_number}</strong>
                          <span className={`status-pill ${buildStatusTone(meter.current_status)}`}>
                            {formatStatusLabel(meter.current_status)}
                          </span>
                        </div>
                        <div className="command-list-item-meta">
                          <span>Meter {meter.id}</span>
                          <span>{meter.utility_meter_number ?? "No utility meter number"}</span>
                        </div>
                        <div className="command-list-item-meta">
                          <span>
                            {meter.communication_profile_code ??
                              meter.meter_profile_code ??
                              "No profile summary"}
                          </span>
                          <span>Last seen {formatDateTime(meter.last_seen_at)}</span>
                        </div>
                        <div className="artifact-row">
                          <label className="artifact-pill">
                            <input
                              checked={isSelected}
                              onChange={() => toggleWizardMeterSelection(meter.id)}
                              type="checkbox"
                            />{" "}
                            Include in bulk request
                          </label>
                        </div>
                      </article>
                    );
                  })}
                </div>

                {bulkSubmissionResult ? (
                  <div className="detail-grid">
                    {bulkSubmissionResult.items.slice(0, 4).map((item) => (
                      <div key={`${item.meter_id}-${item.command_id ?? item.submission_status}`} className="stat-card">
                        <span className="stat-label">Target {item.meter_id}</span>
                        <strong>
                          {item.command_id
                            ? item.command_template_code ?? "Command created"
                            : "Submission needs follow-up"}
                        </strong>
                        <p className="muted">{item.detail ?? "No detail recorded."}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </form>
            )}
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Approvals queue</h2>
                <p className="muted">
                  Bounded queue and recent decision visibility for commands routed through the
                  current one-step approvals MVP.
                </p>
              </div>
              <span className="artifact-pill">{filteredPendingApprovals.length} waiting</span>
            </div>

            {approvalActionError ? <p className="error-banner">{approvalActionError}</p> : null}
            {approvalActionSuccess ? (
              <p className="success-banner">{approvalActionSuccess}</p>
            ) : null}

            <div className="inline-form">
              <label className="field">
                <span>Approval family</span>
                <select
                  onChange={(event) =>
                    setApprovalFamilyFilter(event.target.value as ApprovalFamilyFilter)
                  }
                  value={approvalFamilyFilter}
                >
                  <option value="all">All approval families</option>
                  <option value="relay_control">Relay control</option>
                  <option value="on_demand_read">On-demand read</option>
                </select>
              </label>
              <label className="field">
                <span>Approval search</span>
                <input
                  aria-label="Approval search"
                  onChange={(event) => setApprovalSearchQuery(event.target.value)}
                  placeholder="Search template, meter, family, status, or approval note"
                  type="search"
                  value={approvalSearchQuery}
                />
              </label>
            </div>

            <div className="artifact-row">
              <span className="artifact-pill">
                {approvalFamilyFilter === "all"
                  ? "All approval families in view"
                  : `${formatCommandFamilyLabel(approvalFamilyFilter)} approvals only`}
              </span>
              <span className="artifact-pill">
                {filteredPendingApprovals.length} pending review item
                {filteredPendingApprovals.length === 1 ? "" : "s"}
              </span>
              <span className="artifact-pill">
                {filteredApprovalHistoryItems.length} recent decision
                {filteredApprovalHistoryItems.length === 1 ? "" : "s"} visible
              </span>
            </div>

            {isLoadingPendingApprovals ? (
              <p className="muted">Loading pending approvals...</p>
            ) : null}

            {!isLoadingPendingApprovals && filteredPendingApprovals.length === 0 ? (
              <p className="muted">
                {approvalSearchQuery.trim() || approvalFamilyFilter !== "all"
                  ? "No pending approvals match the current approval filters."
                  : "No commands are currently waiting in the bounded approvals queue."}
              </p>
            ) : null}

            <div className="command-list">
              {filteredPendingApprovals.map((command) => (
                <article key={command.command_id} className="command-list-item">
                  <div className="command-list-item-header">
                    <strong>{command.command_template_code}</strong>
                    <span className={`status-pill ${buildStatusTone(command.approval_status)}`}>
                      {formatStatusLabel(command.approval_status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {formatCommandFamilyLabel(command.command_family)}
                    </span>
                    <span className="artifact-pill">{formatStatusLabel(command.command_status)}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter {command.meter_id}</span>
                    <span>Requested {formatDateTime(command.created_at)}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                    <span>Last updated {formatDateTime(command.latest_updated_at)}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Next action approve or reject</span>
                    <span>Awaiting one-step operator review</span>
                  </div>
                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedCommandId(command.command_id)}
                      type="button"
                    >
                      Inspect
                    </button>
                    <button
                      className="primary-button"
                      disabled={activeApprovalActionCommandId === command.command_id}
                      onClick={() => void handleApprovalAction(command.command_id, "approve")}
                      type="button"
                    >
                      Approve
                    </button>
                    <button
                      className="secondary-button"
                      disabled={activeApprovalActionCommandId === command.command_id}
                      onClick={() => void handleApprovalAction(command.command_id, "reject")}
                      type="button"
                    >
                      Reject
                    </button>
                  </div>
                </article>
              ))}
            </div>

            <section className="subpanel commands-detail-subpanel">
              <div className="section-heading">
                <div>
                  <h3>Recent approval decisions</h3>
                  <p className="muted">
                    Latest approved and rejected decisions visible from the bounded commands
                    read model.
                  </p>
                </div>
                <label className="inline-select">
                  <span>Decision state</span>
                  <select
                    onChange={(event) =>
                      setApprovalHistoryFilter(event.target.value as ApprovalHistoryFilter)
                    }
                    value={approvalHistoryFilter}
                  >
                    <option value="all_decisions">Approved + rejected</option>
                    <option value="approved">Approved only</option>
                    <option value="rejected">Rejected only</option>
                  </select>
                </label>
              </div>

              {isLoadingApprovalHistory ? (
                <p className="muted">Loading recent approval decisions...</p>
              ) : null}

              {!isLoadingApprovalHistory && filteredApprovalHistoryItems.length === 0 ? (
                <p className="muted">
                  {approvalSearchQuery.trim() ||
                  approvalFamilyFilter !== "all" ||
                  approvalHistoryFilter !== "all_decisions"
                    ? "No recent approval decisions match the current filters."
                    : "No recent approval decisions are currently visible."}
                </p>
              ) : null}

              <div className="command-list">
                {filteredApprovalHistoryItems.map((command) => (
                  <article key={command.command_id} className="command-list-item">
                    <div className="command-list-item-header">
                      <strong>{command.command_template_code}</strong>
                      <span className={`status-pill ${buildStatusTone(command.approval_status)}`}>
                        {formatStatusLabel(command.approval_status)}
                      </span>
                    </div>
                    <div className="command-list-item-badges">
                      <span className="artifact-pill">
                        {formatCommandFamilyLabel(command.command_family)}
                      </span>
                      <span className="artifact-pill">
                        Runtime {formatStatusLabel(command.command_status)}
                      </span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>Meter {command.meter_id}</span>
                      <span>Reviewed {formatDateTime(command.approval_reviewed_at)}</span>
                    </div>
                    <div className="command-list-item-meta">
                      <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                      <span>{command.approval_notes ?? "No approval note recorded"}</span>
                    </div>
                    <div className="artifact-row">
                      <button
                        className="secondary-button"
                        onClick={() => setSelectedCommandId(command.command_id)}
                        type="button"
                      >
                        Inspect decision
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </section>
        </div>

        <div className="commands-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Recent commands</h2>
                <p className="muted">
                  Global operational list for the stable command families only.
                </p>
              </div>
              <label className="inline-select">
                <span>Family</span>
                <select
                  value={recentFamilyFilter}
                  onChange={(event) =>
                    setRecentFamilyFilter(event.target.value as FamilyFilter)
                  }
                >
                  <option value="all">All supported</option>
                  <option value="profile_capture">Profile capture</option>
                  <option value="relay_control">Relay control</option>
                  <option value="on_demand_read">On-demand read</option>
                </select>
              </label>
            </div>

            {isLoadingRecentCommands ? (
              <p className="muted">Loading recent commands...</p>
            ) : null}

            {!isLoadingRecentCommands && recentCommands.length > 0 ? (
              <div className="commands-selection-summary">
                <span className="muted">
                  {recentCommands.length} commands loaded from the current operational
                  view.
                </span>
                {selectedRecentCommand ? (
                  <span className="artifact-pill">
                    Selected: {selectedRecentCommand.command_template_code}
                  </span>
                ) : null}
              </div>
            ) : null}

            <div className="command-list">
              {recentCommands.length === 0 ? (
                <p className="muted">No supported recent commands available.</p>
              ) : null}

              {recentCommands.map((command) => (
                <button
                  key={command.command_id}
                  className={
                    selectedCommandId === command.command_id
                      ? "command-list-item selected"
                      : "command-list-item"
                  }
                  onClick={() => setSelectedCommandId(command.command_id)}
                  type="button"
                >
                  <div className="command-list-item-header">
                    <strong>{command.command_template_code}</strong>
                    <span className={`status-pill ${buildStatusTone(command.command_status)}`}>
                      {formatStatusLabel(command.command_status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {formatCommandFamilyLabel(command.command_family)}
                    </span>
                    <span className="artifact-pill">
                      {formatCommandCategoryLabel(command.command_category)}
                    </span>
                    <span className={`status-pill ${buildStatusTone(command.approval_status)}`}>
                      Approval {formatStatusLabel(command.approval_status)}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter {command.meter_id}</span>
                    <span>
                      Attempt {formatStatusLabel(command.latest_command_execution_attempt_status)}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{formatFamilySummary(command.family_specific_outcome_summary)}</span>
                    <span>Updated {formatDateTime(command.latest_updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Command detail</h2>
                <p className="muted">
                  Bounded detail projection for the selected recent command.
                </p>
              </div>
            </div>

            {isLoadingDetail ? <p className="muted">Loading command detail...</p> : null}
            {detailError ? <p className="error-banner">{detailError}</p> : null}

            {selectedCommandDetail ? (
              <div className="detail-stack">
                <section className="commands-detail-hero">
                  <div className="commands-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Command</p>
                      <h3>{selectedCommandDetail.command_template_code}</h3>
                      <p className="muted">
                        {formatCommandFamilyLabel(selectedCommandDetail.command_family)} routed
                        through the current{" "}
                        {formatCommandCategoryLabel(selectedCommandDetail.command_category)}{" "}
                        projection.
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(
                        selectedCommandDetail.command_status,
                      )}`}
                    >
                      {formatStatusLabel(selectedCommandDetail.command_status)}
                    </span>
                  </div>

                  <div className="commands-detail-badges">
                    <span className="artifact-pill">
                      {formatCommandFamilyLabel(selectedCommandDetail.command_family)}
                    </span>
                    <span className="artifact-pill">
                      {formatCommandCategoryLabel(selectedCommandDetail.command_category)}
                    </span>
                    <span className={`status-pill ${buildStatusTone(selectedCommandDetail.approval_status)}`}>
                      Approval {formatStatusLabel(selectedCommandDetail.approval_status)}
                    </span>
                    <span className="artifact-pill">
                      Outcome:{" "}
                      {formatFamilySummary(
                        selectedCommandDetail.family_specific_outcome_summary,
                      )}
                    </span>
                  </div>
                </section>

                <div className="detail-grid">
                  <div className="stat-card">
                    <span className="stat-label">Meter ID</span>
                    <strong>{selectedCommandDetail.meter_id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Family</span>
                    <strong>
                      {formatCommandFamilyLabel(selectedCommandDetail.command_family)}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Category</span>
                    <strong>
                      {formatCommandCategoryLabel(selectedCommandDetail.command_category)}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Status</span>
                    <strong>{formatStatusLabel(selectedCommandDetail.command_status)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Approval status</span>
                    <strong>{formatStatusLabel(selectedCommandDetail.approval_status)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Approval reviewed</span>
                    <strong>{formatDateTime(selectedCommandDetail.approval_reviewed_at)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Latest attempt</span>
                    <strong>
                      {formatStatusLabel(
                        selectedCommandDetail.latest_command_execution_attempt_status,
                      )}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Outcome summary</span>
                    <strong>
                      {formatFamilySummary(
                        selectedCommandDetail.family_specific_outcome_summary,
                      )}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Runtime execution record</span>
                    <strong>
                      {selectedCommandDetail.runtime_execution_record_id ?? "Not recorded"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Created</span>
                    <strong>{formatDateTime(selectedCommandDetail.created_at)}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Last updated</span>
                    <strong>{formatDateTime(selectedCommandDetail.latest_updated_at)}</strong>
                  </div>
                </div>

                <section className="subpanel commands-detail-subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Approval context</h3>
                      <p className="muted">
                        One-step approval visibility for the bounded bulk command MVP.
                      </p>
                    </div>
                  </div>
                  <div className="detail-grid">
                    <div className="stat-card">
                      <span className="stat-label">Approval status</span>
                      <strong>{formatStatusLabel(selectedCommandDetail.approval_status)}</strong>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Approval note</span>
                      <strong>{selectedCommandDetail.approval_notes ?? "Not recorded"}</strong>
                    </div>
                  </div>
                </section>

                <section className="subpanel commands-detail-subpanel">
                  <div className="section-heading">
                    <div>
                      <h3>Outcome and artifacts</h3>
                      <p className="muted">
                        Family-specific outcome summary and orchestration artifact presence
                        from the current stable commands read model.
                      </p>
                    </div>
                  </div>

                  {projectionEntries.length > 0 ? (
                    <div className="detail-grid">
                      {projectionEntries.map(([key, value]) => (
                        <div key={key} className="stat-card">
                          <span className="stat-label">{formatProjectionKey(key)}</span>
                          <strong>{value}</strong>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted">
                      No family-specific outcome fields are currently recorded.
                    </p>
                  )}

                  <div className="artifact-row">
                    <span className="artifact-pill">
                      execute-now:{" "}
                      {selectedCommandDetail.execute_now_artifact_present
                        ? "present"
                        : "absent"}
                    </span>
                    <span className="artifact-pill">
                      orchestration:{" "}
                      {selectedCommandDetail.orchestration_artifact_present
                        ? "present"
                        : "absent"}
                    </span>
                    <span className="artifact-pill">
                      terminalization:{" "}
                      {selectedCommandDetail.terminalization_artifact_present
                        ? "present"
                        : "absent"}
                    </span>
                  </div>
                </section>

                <div className="json-panel">
                  <h3>Projection record</h3>
                  <pre>
                    {JSON.stringify(selectedCommandDetail.projection_record, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <p className="muted">Select a recent command to load bounded command detail.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
