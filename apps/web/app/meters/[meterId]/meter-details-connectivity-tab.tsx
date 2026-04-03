"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type MeterDetail = {
  id: string;
  communication_profile_code: string | null;
  last_seen_at: string | null;
  current_status: string;
};

type MeterEndpointAssignment = {
  id: string;
  endpoint_id: string;
  endpoint_code: string;
  endpoint_display_name: string;
  assignment_status: string;
  is_primary: boolean;
};

type ProtocolAssociationProfile = {
  id: string;
  code: string;
  name: string;
  protocol_family: string;
  is_active: boolean;
};

type ConnectivitySession = {
  id: string;
  meter_id: string | null;
  endpoint_id: string | null;
  protocol_association_profile_id: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  session_purpose: string;
  request_id: string | null;
  correlation_id: string | null;
  error_code: string | null;
  error_message: string | null;
  bytes_sent: number | null;
  bytes_received: number | null;
  transport_latency_ms: number | null;
  handshake_stage: string | null;
  metadata: Record<string, unknown> | null;
};

type ConnectivitySessionHistoryListResponse = {
  total: number;
  items: ConnectivitySession[];
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

function formatStatusLabel(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  return value
    .split(/[_\s/.-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatConnectivityFreshnessHint(lastSeenAt: string | null): string {
  return lastSeenAt ? "Recent connectivity signal recorded" : "No recent connectivity signal";
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("succeed") ||
    normalized.includes("active") ||
    normalized.includes("healthy") ||
    normalized.includes("connected")
  ) {
    return "positive";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("offline") ||
    normalized.includes("cancel")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("warning") ||
    normalized.includes("timed") ||
    normalized.includes("stale") ||
    normalized.includes("degraded")
  ) {
    return "warning";
  }
  return "neutral";
}

function buildLatestSessionSummary(session: ConnectivitySession | null): string {
  if (!session) {
    return "No recent session recorded";
  }
  return `${formatStatusLabel(session.status)} (${formatStatusLabel(session.session_purpose)})`;
}

function buildConnectivityHealthLabel({
  meter,
  latestSession,
}: {
  meter: MeterDetail | null;
  latestSession: ConnectivitySession | null;
}): string {
  if (latestSession?.status) {
    return formatStatusLabel(latestSession.status);
  }
  if (meter?.last_seen_at) {
    return "Signal present";
  }
  return "No active signal";
}

export function MeterDetailsConnectivityTab({
  meterId,
  meter,
  primaryEndpointAssignment,
  defaultProtocolProfile,
  hasConnectivityContext,
  isConnectivityContextLoading,
  authorizedFetch,
}: {
  meterId: string;
  meter: MeterDetail | null;
  primaryEndpointAssignment: MeterEndpointAssignment | null;
  defaultProtocolProfile: ProtocolAssociationProfile | null;
  hasConnectivityContext: boolean;
  isConnectivityContextLoading: boolean;
  authorizedFetch: AuthorizedFetch;
}) {
  const [sessions, setSessions] = useState<ConnectivitySession[]>([]);
  const [totalSessions, setTotalSessions] = useState(0);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setSessionError(null);

    try {
      const response = await authorizedFetch<ConnectivitySessionHistoryListResponse>(
        `/api/v1/meters/${meterId}/sessions?limit=5`,
      );
      setSessions(response.items);
      setTotalSessions(response.total);
    } catch (error) {
      setSessions([]);
      setTotalSessions(0);
      setSessionError(
        error instanceof Error
          ? error.message
          : "Unable to load meter connectivity sessions.",
      );
    } finally {
      setIsLoadingSessions(false);
    }
  }, [authorizedFetch, meterId]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const latestSession = sessions[0] ?? null;
  const hasAnyConnectivityVisibility =
    hasConnectivityContext || latestSession !== null || meter?.last_seen_at != null;

  const overviewCards = useMemo(
    () => [
      {
        label: "Connectivity health",
        value: buildConnectivityHealthLabel({ meter, latestSession }),
        note: latestSession
          ? buildLatestSessionSummary(latestSession)
          : formatConnectivityFreshnessHint(meter?.last_seen_at ?? null),
      },
      {
        label: "Last seen",
        value: formatDateTime(meter?.last_seen_at ?? null),
        note: formatConnectivityFreshnessHint(meter?.last_seen_at ?? null),
      },
      {
        label: "Primary endpoint",
        value:
          primaryEndpointAssignment?.endpoint_display_name ??
          primaryEndpointAssignment?.endpoint_code ??
          "No active endpoint",
        note: primaryEndpointAssignment
          ? `${formatStatusLabel(primaryEndpointAssignment.assignment_status)} • ${primaryEndpointAssignment.is_primary ? "Primary assignment" : "Secondary assignment"}`
          : "No endpoint assignment recorded",
      },
      {
        label: "Protocol context",
        value:
          defaultProtocolProfile?.code ?? meter?.communication_profile_code ?? "Not available",
        note: defaultProtocolProfile
          ? `${formatStatusLabel(defaultProtocolProfile.protocol_family)} profile`
          : meter?.communication_profile_code ?? "No protocol profile recorded",
      },
      {
        label: "Recent sessions",
        value: String(sessions.length),
        note:
          totalSessions > sessions.length
            ? `${totalSessions} sessions available in current history`
            : "Current bounded session history result set",
      },
      {
        label: "Latest handshake stage",
        value: latestSession?.handshake_stage
          ? formatStatusLabel(latestSession.handshake_stage)
          : "Not available",
        note: latestSession?.error_code ?? latestSession?.error_message ?? "No current handshake error recorded",
      },
    ],
    [
      defaultProtocolProfile,
      hasConnectivityContext,
      latestSession,
      meter,
      primaryEndpointAssignment,
      sessions.length,
      totalSessions,
    ],
  );

  return (
    <div className="detail-stack">
      {sessionError ? <p className="error-banner">{sessionError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Connectivity context</h2>
            <p className="muted">
              Meter-scoped communication health, endpoint context, and bounded session
              history using the existing connectivity read model.
            </p>
          </div>
          <div className="artifact-row">
            <span className="artifact-pill">
              {isLoadingSessions
                ? "Loading session history"
                : `${totalSessions} session${totalSessions === 1 ? "" : "s"} in scope`}
            </span>
            <Link className="secondary-button" href="/connectivity">
              Open connectivity surface
            </Link>
          </div>
        </div>

        {isConnectivityContextLoading || isLoadingSessions ? (
          <p className="muted">Loading connectivity context...</p>
        ) : null}

        {!isConnectivityContextLoading && !isLoadingSessions && hasAnyConnectivityVisibility ? (
          <div className="detail-stack">
            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>

            <div className="artifact-row">
              <span className={`status-pill ${buildStatusTone(latestSession?.status ?? meter?.current_status ?? null)}`}>
                {buildConnectivityHealthLabel({ meter, latestSession })}
              </span>
              <span className="artifact-pill">
                {buildLatestSessionSummary(latestSession)}
              </span>
              <span className="artifact-pill">
                {formatConnectivityFreshnessHint(meter?.last_seen_at ?? null)}
              </span>
            </div>
          </div>
        ) : null}

        {!isConnectivityContextLoading && !isLoadingSessions && !hasAnyConnectivityVisibility ? (
          <p className="muted">Connectivity context not available.</p>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Recent session history</h2>
            <p className="muted">
              Latest meter-scoped connectivity sessions with status, purpose, and bounded
              transport detail.
            </p>
          </div>
        </div>

        {isLoadingSessions ? (
          <p className="muted">Loading connectivity session history...</p>
        ) : sessions.length === 0 ? (
          <section className="audit-center-empty-state">
            <p className="eyebrow">Session History Empty</p>
            <h3>No connectivity sessions are currently recorded for this meter</h3>
            <p className="muted">
              Endpoint and freshness context may still be visible above, but there is no
              recent session history available for this operational record.
            </p>
          </section>
        ) : (
          <div className="meter-summary-grid">
            {sessions.map((session) => (
              <div key={session.id} className="stat-card">
                <span className="stat-label">{formatStatusLabel(session.session_purpose)}</span>
                <strong>{formatStatusLabel(session.status)}</strong>
                <p className="muted">Started {formatDateTime(session.started_at)}</p>
                <p className="muted">Ended {formatDateTime(session.ended_at)}</p>
                <p className="muted">
                  {session.handshake_stage
                    ? `Handshake ${formatStatusLabel(session.handshake_stage)}`
                    : "No handshake stage recorded"}
                </p>
                <p className="muted">
                  {session.error_message ??
                    session.error_code ??
                    (session.transport_latency_ms != null
                      ? `Latency ${session.transport_latency_ms} ms`
                      : "No transport error recorded")}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
