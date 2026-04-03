"use client";

import { useMemo } from "react";

type MeterDetail = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  current_status: string;
  transformer_id: string | null;
  service_point_id: string | null;
  last_seen_at: string | null;
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

export function MeterDetailsAttachmentsTab({
  meter,
  linkedServicePointId,
  linkedServicePointCode,
  isAttachmentsContextLoading,
  attachmentsContextError,
}: {
  meter: MeterDetail | null;
  linkedServicePointId: string | null;
  linkedServicePointCode: string | null;
  isAttachmentsContextLoading: boolean;
  attachmentsContextError: string | null;
}) {
  const overviewCards = useMemo(
    () => [
      {
        label: "Attachment coverage",
        value: "No current attachment source",
        note: "The current repo does not expose a meter-linked attachments or documents read model.",
      },
      {
        label: "Visible attachments",
        value: "0",
        note: "No real meter attachment records are available to show in this bounded slice today.",
      },
      {
        label: "Primary attachment anchor",
        value: meter?.serial_number ?? meter?.id ?? "Not available",
        note: meter ? `Meter ${meter.id}` : "Meter record unavailable",
      },
      {
        label: "Related installation anchor",
        value:
          linkedServicePointCode ??
          linkedServicePointId ??
          meter?.service_point_id ??
          meter?.transformer_id ??
          "Not available",
        note: meter?.transformer_id
          ? `Transformer ${meter.transformer_id}`
          : "No service-point or transformer attachment anchor in scope",
      },
    ],
    [linkedServicePointCode, linkedServicePointId, meter],
  );

  return (
    <div className="detail-stack">
      {attachmentsContextError ? <p className="error-banner">{attachmentsContextError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>Attachments context</h2>
            <p className="muted">
              Read-only attachment visibility for the current meter using the existing repo
              contracts. This slice stays honest when no attachment foundation exists.
            </p>
          </div>
        </div>

        {isAttachmentsContextLoading ? <p className="muted">Loading attachments context...</p> : null}

        {!isAttachmentsContextLoading ? (
          <div className="detail-stack">
            <p className="muted">
              No meter-linked files or documents are currently exposed by the existing
              application contracts. This bounded tab reserves the operational slot without
              inventing attachment records.
            </p>

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
            <h2>Attachment anchors</h2>
            <p className="muted">
              Current meter identifiers and installation context that would naturally scope
              future attachment linkage.
            </p>
          </div>
        </div>

        {isAttachmentsContextLoading && !meter ? (
          <p className="muted">Loading attachment anchors...</p>
        ) : null}

        {!isAttachmentsContextLoading && meter ? (
          <div className="detail-grid">
            <div className="stat-card">
              <span className="stat-label">Meter ID</span>
              <strong>{meter.id}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Serial number</span>
              <strong>{meter.serial_number}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Utility meter number</span>
              <strong>{meter.utility_meter_number ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Lifecycle</span>
              <strong>{formatStatusLabel(meter.current_status)}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Service point</span>
              <strong>
                {linkedServicePointCode ?? linkedServicePointId ?? meter.service_point_id ?? "Not available"}
              </strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Transformer</span>
              <strong>{meter.transformer_id ?? "Not available"}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Last seen</span>
              <strong>{formatDateTime(meter.last_seen_at)}</strong>
            </div>
            <div className="stat-card">
              <span className="stat-label">Attachment status</span>
              <strong>No registered attachments</strong>
            </div>
          </div>
        ) : null}

        {!isAttachmentsContextLoading && !meter ? (
          <p className="muted">Attachments context not available for this meter.</p>
        ) : null}
      </section>
    </div>
  );
}
