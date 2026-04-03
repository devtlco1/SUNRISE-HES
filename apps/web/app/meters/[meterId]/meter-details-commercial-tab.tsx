"use client";

import Link from "next/link";
import { useMemo } from "react";

type MeterConsumerLinkage = {
  meter_id: string;
  linkage_status: string;
  linkage_source: string | null;
  consumer_id: string | null;
  consumer_display_name: string | null;
  consumer_type: string | null;
  consumer_external_ref: string | null;
  account_id: string | null;
  account_number: string | null;
  account_status: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
};

function formatLabel(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  return value
    .split(/[._]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function MeterDetailsCommercialTab({
  consumerLinkage,
  isLoadingConsumerLinkage,
  consumerLinkageError,
  linkedServicePointId,
  linkedServicePointCode,
}: {
  consumerLinkage: MeterConsumerLinkage | null;
  isLoadingConsumerLinkage: boolean;
  consumerLinkageError: string | null;
  linkedServicePointId: string | null;
  linkedServicePointCode: string | null;
}) {
  const commercialCards = useMemo(
    () => [
      {
        label: "Linkage status",
        value: formatLabel(consumerLinkage?.linkage_status ?? "unlinked"),
        note:
          consumerLinkage?.linkage_source != null
            ? `Source ${formatLabel(consumerLinkage.linkage_source)}`
            : "No current linkage source recorded",
      },
      {
        label: "Subscriber identity",
        value: consumerLinkage?.consumer_display_name ?? "No linked subscriber",
        note:
          consumerLinkage?.consumer_external_ref ??
          consumerLinkage?.consumer_type ??
          "No subscriber reference recorded",
      },
      {
        label: "Account identity",
        value: consumerLinkage?.account_number ?? "No linked account",
        note: consumerLinkage?.account_status ?? "No account status recorded",
      },
      {
        label: "Service point context",
        value: linkedServicePointCode ?? linkedServicePointId ?? "No linked service point",
        note: linkedServicePointId ? "Current commercial service location in scope" : "No service point linkage recorded",
      },
    ],
    [consumerLinkage, linkedServicePointCode, linkedServicePointId],
  );

  return (
    <div className="detail-stack">
      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Consumer / commercial context</h2>
            <p className="muted">
              Current subscriber, account, and service context already linked to this meter.
            </p>
          </div>
        </div>

        {isLoadingConsumerLinkage ? (
          <p className="muted">Loading consumer / commercial context...</p>
        ) : null}

        {!isLoadingConsumerLinkage && consumerLinkageError ? (
          <p className="error-banner">{consumerLinkageError}</p>
        ) : null}

        {!isLoadingConsumerLinkage && !consumerLinkageError ? (
          <div className="detail-stack">
            <div className="meter-summary-grid">
              {commercialCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>

            <div className="artifact-row">
              <span className="artifact-pill">
                Linkage {formatLabel(consumerLinkage?.linkage_status ?? "unlinked")}
              </span>
              <span className="artifact-pill">
                {consumerLinkage?.linkage_source
                  ? `Source ${formatLabel(consumerLinkage.linkage_source)}`
                  : "Existing meter linkage only"}
              </span>
            </div>
          </div>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Commercial navigation</h2>
            <p className="muted">
              Continue into the existing subscriber, account, and service-point surfaces when
              a deeper commercial investigation is needed.
            </p>
          </div>
        </div>

        {isLoadingConsumerLinkage ? (
          <p className="muted">Loading commercial navigation context...</p>
        ) : null}

        {!isLoadingConsumerLinkage &&
        !consumerLinkageError &&
        consumerLinkage?.linkage_status === "linked" ? (
          <div className="detail-stack">
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Subscriber</span>
                <strong>{consumerLinkage.consumer_display_name ?? "Linked subscriber"}</strong>
                <p className="muted">{consumerLinkage.consumer_id ?? "No subscriber ID recorded"}</p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Account</span>
                <strong>{consumerLinkage.account_number ?? "Linked account"}</strong>
                <p className="muted">{consumerLinkage.account_status ?? "No account status recorded"}</p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Service point</span>
                <strong>{linkedServicePointCode ?? linkedServicePointId ?? "Not available"}</strong>
                <p className="muted">Current service location linked to this meter</p>
              </div>
            </div>

            <div className="artifact-row">
              {consumerLinkage.consumer_id ? (
                <Link
                  className="primary-button"
                  href={`/subscribers/${consumerLinkage.consumer_id}`}
                >
                  Open subscriber detail
                </Link>
              ) : null}
              {consumerLinkage.account_id ? (
                <Link className="secondary-button" href={`/accounts/${consumerLinkage.account_id}`}>
                  Open account detail
                </Link>
              ) : null}
              {linkedServicePointId ? (
                <Link
                  className="secondary-button"
                  href={`/service-points/${linkedServicePointId}`}
                >
                  Open service point detail
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}

        {!isLoadingConsumerLinkage &&
        !consumerLinkageError &&
        consumerLinkage?.linkage_status !== "linked" ? (
          <section className="audit-center-empty-state">
            <p className="eyebrow">Commercial Context Empty</p>
            <h3>No linked subscriber or account is currently attached to this meter</h3>
            <p className="muted">
              This meter remains visible operationally, but no active commercial linkage is
              currently available through the existing consumer/account assignment path.
            </p>
            {linkedServicePointId ? (
              <div className="artifact-row">
                <Link
                  className="secondary-button"
                  href={`/service-points/${linkedServicePointId}`}
                >
                  Open service point detail
                </Link>
              </div>
            ) : null}
          </section>
        ) : null}
      </section>
    </div>
  );
}
