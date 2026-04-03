"use client";

import Link from "next/link";
import { useMemo } from "react";

type MeterDetail = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  meter_profile_code: string | null;
  communication_profile_code: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  last_seen_at: string | null;
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

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("active") ||
    normalized.includes("commission") ||
    normalized.includes("connected")
  ) {
    return "positive";
  }
  if (
    normalized.includes("error") ||
    normalized.includes("fail") ||
    normalized.includes("inactive") ||
    normalized.includes("retired")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("staged") ||
    normalized.includes("draft")
  ) {
    return "warning";
  }
  return "neutral";
}

function buildCoverageLabel({
  meter,
  primaryEndpointAssignment,
  defaultProtocolProfile,
}: {
  meter: MeterDetail | null;
  primaryEndpointAssignment: MeterEndpointAssignment | null;
  defaultProtocolProfile: ProtocolAssociationProfile | null;
}): string {
  const configuredSignals = [
    meter?.meter_profile_code,
    meter?.communication_profile_code,
    primaryEndpointAssignment?.endpoint_code,
    defaultProtocolProfile?.code,
  ].filter(Boolean).length;

  if (configuredSignals >= 4) {
    return "Well aligned";
  }
  if (configuredSignals >= 2) {
    return "Partially aligned";
  }
  if (configuredSignals >= 1) {
    return "Catalog only";
  }
  return "Configuration gaps";
}

export function MeterDetailsConfigurationTab({
  meter,
  primaryEndpointAssignment,
  activeEndpointAssignments,
  defaultProtocolProfile,
  activeProtocolProfiles,
  linkedServicePointId,
  linkedServicePointCode,
  isConfigurationContextLoading,
  configurationContextError,
}: {
  meter: MeterDetail | null;
  primaryEndpointAssignment: MeterEndpointAssignment | null;
  activeEndpointAssignments: MeterEndpointAssignment[];
  defaultProtocolProfile: ProtocolAssociationProfile | null;
  activeProtocolProfiles: ProtocolAssociationProfile[];
  linkedServicePointId: string | null;
  linkedServicePointCode: string | null;
  isConfigurationContextLoading: boolean;
  configurationContextError: string | null;
}) {
  const hasOperationalConfigurationContext =
    meter?.meter_profile_code != null ||
    meter?.communication_profile_code != null ||
    primaryEndpointAssignment !== null ||
    defaultProtocolProfile !== null;

  const overviewCards = useMemo(
    () => [
      {
        label: "Configuration coverage",
        value: buildCoverageLabel({
          meter,
          primaryEndpointAssignment,
          defaultProtocolProfile,
        }),
        note: hasOperationalConfigurationContext
          ? "Meter catalog, profile, endpoint, and protocol context are partially or fully visible."
          : "Only the bounded catalog record is visible right now.",
      },
      {
        label: "Manufacturer / model",
        value: meter ? `${meter.manufacturer_code} / ${meter.meter_model_code}` : "Not available",
        note: meter?.utility_meter_number
          ? `Utility meter number ${meter.utility_meter_number}`
          : "No utility meter number recorded",
      },
      {
        label: "Meter profile",
        value: meter?.meter_profile_code ?? "Not recorded",
        note: meter ? `Lifecycle ${formatStatusLabel(meter.current_status)}` : "Meter detail unavailable",
      },
      {
        label: "Communication profile",
        value: meter?.communication_profile_code ?? "Not recorded",
        note: primaryEndpointAssignment
          ? `${primaryEndpointAssignment.endpoint_display_name} in active scope`
          : "No active endpoint assignment recorded",
      },
      {
        label: "Protocol profile",
        value: defaultProtocolProfile?.code ?? "No active protocol profile",
        note: defaultProtocolProfile
          ? `${formatStatusLabel(defaultProtocolProfile.protocol_family)} • ${defaultProtocolProfile.name}`
          : "No active protocol profile recorded",
      },
      {
        label: "Firmware / version",
        value: "Not recorded",
        note: "The current meter detail contract does not expose a firmware/version field.",
      },
    ],
    [
      defaultProtocolProfile,
      hasOperationalConfigurationContext,
      meter,
      primaryEndpointAssignment,
    ],
  );

  return (
    <div className="detail-stack">
      {configurationContextError ? <p className="error-banner">{configurationContextError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Configuration context</h2>
            <p className="muted">
              Meter-scoped model, profile, protocol, and installation visibility using the
              existing meter detail record and current endpoint/protocol context.
            </p>
          </div>
        </div>

        {isConfigurationContextLoading ? (
          <p className="muted">Loading configuration context...</p>
        ) : null}

        {!isConfigurationContextLoading ? (
          <div className="detail-stack">
            {!configurationContextError && !hasOperationalConfigurationContext ? (
              <p className="muted">
                No active profile or endpoint configuration is currently recorded for this
                meter. The bounded catalog record is still shown below.
              </p>
            ) : null}

            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Operational configuration record</h2>
            <p className="muted">
              Read-only configuration cues for the current meter definition, protocol
              alignment, and installation context.
            </p>
          </div>
        </div>

        {isConfigurationContextLoading && !meter ? (
          <p className="muted">Loading configuration record...</p>
        ) : null}

        {!isConfigurationContextLoading && meter ? (
          <div className="detail-stack">
            <div className="detail-grid">
              <div className="stat-card">
                <span className="stat-label">Serial number</span>
                <strong>{meter.serial_number}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Meter ID</span>
                <strong>{meter.id}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Lifecycle</span>
                <strong>{formatStatusLabel(meter.current_status)}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Last seen</span>
                <strong>{formatDateTime(meter.last_seen_at)}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Primary endpoint</span>
                <strong>
                  {primaryEndpointAssignment?.endpoint_display_name ??
                    primaryEndpointAssignment?.endpoint_code ??
                    "Not available"}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Endpoint assignment state</span>
                <strong>
                  {formatStatusLabel(primaryEndpointAssignment?.assignment_status ?? null)}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Active endpoint assignments</span>
                <strong>{String(activeEndpointAssignments.length)}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Protocol family</span>
                <strong>
                  {defaultProtocolProfile
                    ? formatStatusLabel(defaultProtocolProfile.protocol_family)
                    : "Not available"}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Active protocol profiles</span>
                <strong>{String(activeProtocolProfiles.length)}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Service point</span>
                <strong>{linkedServicePointCode ?? linkedServicePointId ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Transformer</span>
                <strong>{meter.transformer_id ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Communication profile state</span>
                <strong
                  className={`status-pill ${buildStatusTone(
                    meter.communication_profile_code ?? null,
                  )}`}
                >
                  {meter.communication_profile_code ? "Recorded" : "Missing"}
                </strong>
              </div>
            </div>

            {linkedServicePointId || meter.transformer_id ? (
              <div className="artifact-row">
                {linkedServicePointId ? (
                  <Link className="secondary-button" href={`/service-points/${linkedServicePointId}`}>
                    Open service point detail
                  </Link>
                ) : null}
                {meter.transformer_id ? (
                  <Link
                    className="secondary-button"
                    href={`/transformers-substations/${meter.transformer_id}`}
                  >
                    Open transformer detail
                  </Link>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {!isConfigurationContextLoading && !meter ? (
          <p className="muted">Configuration context not available for this meter.</p>
        ) : null}
      </section>
    </div>
  );
}
