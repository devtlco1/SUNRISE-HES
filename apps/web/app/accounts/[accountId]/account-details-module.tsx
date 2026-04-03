"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type AccountSubscriber = {
  id: string;
  full_name: string;
  consumer_type: string;
  external_ref: string | null;
};

type AccountServicePoint = {
  id: string;
  service_point_code: string;
  address_line: string | null;
  premises_type: string | null;
};

type AccountLinkedMeter = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  current_status: string;
};

type AccountDetail = {
  id: string;
  account_number: string;
  status: string;
  billing_cycle: string | null;
  subscriber: AccountSubscriber;
  service_point: AccountServicePoint | null;
  linked_meter_count: number;
  linked_meters: AccountLinkedMeter[];
};

function formatStatusLabel(value: string): string {
  return value
    .split(/[_\s/]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildStatusTone(value: string | null): "positive" | "warning" | "danger" | "neutral" {
  const normalized = value?.toLowerCase() ?? "";
  if (
    normalized.includes("active") ||
    normalized.includes("registered") ||
    normalized.includes("residential")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("closed") ||
    normalized.includes("blocked") ||
    normalized.includes("suspend")
  ) {
    return "danger";
  }
  if (normalized.includes("pending") || normalized.includes("review")) {
    return "warning";
  }
  return "neutral";
}

function formatServiceContext({
  billingCycle,
  servicePointCode,
}: {
  billingCycle: string | null;
  servicePointCode: string | null;
}): string {
  if (billingCycle && servicePointCode) {
    return `${billingCycle} billing • ${servicePointCode}`;
  }
  if (billingCycle) {
    return `${billingCycle} billing`;
  }
  return servicePointCode ?? "No current service context";
}

export function AccountDetailsModule({
  accountId,
  authorizedFetch,
}: {
  accountId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [detail, setDetail] = useState<AccountDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const loadDetail = useCallback(async () => {
    setIsLoadingDetail(true);
    setDetailError(null);

    try {
      const response = await authorizedFetch<AccountDetail>(
        `/api/v1/accounts/${accountId}`,
      );
      setDetail(response);
    } catch (error) {
      setDetail(null);
      setDetailError(
        error instanceof Error ? error.message : "Unable to load account detail.",
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, [accountId, authorizedFetch]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const primaryLinkedMeter = detail?.linked_meters[0] ?? null;
  const workspaceCards = detail
    ? [
        {
          label: "Account identity",
          value: detail.account_number,
          note: `${formatStatusLabel(detail.status)} • ${detail.id}`,
        },
        {
          label: "Subscriber context",
          value: detail.subscriber.full_name,
          note: `${formatStatusLabel(detail.subscriber.consumer_type)} • ${detail.subscriber.external_ref ?? "No external subscriber identifier"}`,
        },
        {
          label: "Service context",
          value: formatServiceContext({
            billingCycle: detail.billing_cycle,
            servicePointCode: detail.service_point?.service_point_code ?? null,
          }),
          note: detail.service_point?.address_line ?? "No service-point address summary",
        },
        {
          label: "Primary meter",
          value: primaryLinkedMeter?.serial_number ?? "No current linked meter",
          note: primaryLinkedMeter
            ? `${formatStatusLabel(primaryLinkedMeter.current_status)} • ${primaryLinkedMeter.utility_meter_number ?? "No utility number"}`
            : "No active current-meter linkage recorded",
        },
        {
          label: "Premise context",
          value:
            detail.service_point?.premises_type
              ? formatStatusLabel(detail.service_point.premises_type)
              : "Not available",
          note: detail.service_point
            ? `Service point ${detail.service_point.service_point_code}`
            : "No linked service point recorded",
        },
        {
          label: "Linked estate",
          value: `${detail.linked_meter_count} meter(s)`,
          note: "Current account-linked operational meters in the bounded detail result set",
        },
      ]
    : [];

  return (
    <section className="panel">
      {detailError ? <p className="error-banner">{detailError}</p> : null}
      {isLoadingDetail ? <p className="muted">Loading account detail...</p> : null}

      {detail ? (
        <>
          <section className="subpanel accounts-overview-panel">
            <section className="account-detail-hero">
              <div className="account-detail-title-row">
                <div>
                  <p className="eyebrow">Account Detail</p>
                  <h2>{detail.account_number}</h2>
                  <p className="muted">
                    {formatStatusLabel(detail.status)} account with {detail.linked_meter_count} linked
                    current meter(s).
                  </p>
                </div>
                <span className={`status-pill ${buildStatusTone(detail.status)}`}>
                  {formatStatusLabel(detail.status)}
                </span>
              </div>

              <div className="command-list-item-badges">
                <span className="artifact-pill">Account {detail.id}</span>
                <span className="artifact-pill">
                  {detail.subscriber.full_name}
                </span>
                <span className="artifact-pill">
                  {detail.service_point?.service_point_code ?? "No linked service point"}
                </span>
              </div>

              <div className="artifact-row">
                <Link
                  className="primary-button"
                  href={`/subscribers/${detail.subscriber.id}`}
                >
                  Open linked subscriber detail
                </Link>
                {detail.service_point ? (
                  <Link
                    className="secondary-button"
                    href={`/service-points/${detail.service_point.id}`}
                  >
                    Open linked service point detail
                  </Link>
                ) : null}
                {primaryLinkedMeter ? (
                  <Link
                    className="secondary-button"
                    href={`/meters/${primaryLinkedMeter.id}`}
                  >
                    Open primary meter detail
                  </Link>
                ) : null}
              </div>
            </section>

            <div className="accounts-overview-grid">
              <div className="stat-card accounts-overview-card">
                <span className="stat-label">Billing cycle</span>
                <strong>{detail.billing_cycle ?? "Not available"}</strong>
              </div>
              <div className="stat-card accounts-overview-card">
                <span className="stat-label">Subscriber type</span>
                <strong>{formatStatusLabel(detail.subscriber.consumer_type)}</strong>
              </div>
              <div className="stat-card accounts-overview-card">
                <span className="stat-label">Service point</span>
                <strong>{detail.service_point?.service_point_code ?? "Not available"}</strong>
              </div>
              <div className="stat-card accounts-overview-card">
                <span className="stat-label">Linked current meters</span>
                <strong>{detail.linked_meter_count}</strong>
              </div>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Account workspace</h3>
                <p className="muted">
                  Dense operational and commercial summary for the selected account.
                </p>
              </div>
            </div>
            <div className="accounts-overview-grid">
              {workspaceCards.map((card) => (
                <div key={card.label} className="stat-card accounts-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Account summary</h3>
                <p className="muted">
                  Compact identifiers and bounded linked context for the selected account.
                </p>
              </div>
            </div>
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Account ID</span>
                <strong>{detail.id}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Billing cycle</span>
                <strong>{detail.billing_cycle ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Subscriber</span>
                <strong>{detail.subscriber.full_name}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Subscriber type</span>
                <strong>{formatStatusLabel(detail.subscriber.consumer_type)}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Subscriber external reference</span>
                <strong>{detail.subscriber.external_ref ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Service point</span>
                <strong>
                  {detail.service_point?.service_point_code ?? "Not available"}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Linked current meters</span>
                <strong>{detail.linked_meter_count}</strong>
              </div>
            </div>
            <div className="artifact-row">
              <Link
                className="secondary-button"
                href={`/subscribers/${detail.subscriber.id}`}
              >
                Open subscriber detail
              </Link>
              {detail.service_point ? (
                <Link
                  className="secondary-button"
                  href={`/service-points/${detail.service_point.id}`}
                >
                  Open service point detail
                </Link>
              ) : null}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked service point</h3>
                <p className="muted">
                  Bounded service-point visibility for the selected account.
                </p>
              </div>
            </div>
            {detail.service_point ? (
              <div className="meter-list">
                <Link
                  className="meter-list-item"
                  href={`/service-points/${detail.service_point.id}`}
                >
                  <div className="command-list-item-header">
                    <strong>{detail.service_point.service_point_code}</strong>
                    <span
                      className={`status-pill ${buildStatusTone(
                        detail.service_point.premises_type,
                      )}`}
                    >
                      {formatStatusLabel(detail.service_point.premises_type ?? "premise")}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Service point ID {detail.service_point.id}</span>
                    <span>{detail.service_point.address_line ?? "No address summary"}</span>
                  </div>
                </Link>
              </div>
            ) : (
              <p className="muted">No service point linked to this account.</p>
            )}
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked current meters</h3>
                <p className="muted">
                  Current operational meter context for this account.
                </p>
              </div>
              <span className="artifact-pill">{detail.linked_meters.length} meter(s)</span>
            </div>
            <div className="meter-list">
              {detail.linked_meters.length === 0 ? (
                <p className="muted">No current meters linked to this account.</p>
              ) : null}
              {detail.linked_meters.map((meter) => (
                <Link key={meter.id} className="meter-list-item" href={`/meters/${meter.id}`}>
                  <div className="command-list-item-header">
                    <strong>{meter.serial_number}</strong>
                    <span className={`status-pill ${buildStatusTone(meter.current_status)}`}>
                      {formatStatusLabel(meter.current_status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {meter.utility_meter_number ?? "No utility number"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter ID {meter.id}</span>
                    <span>Open existing meter detail</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{detail.account_number}</span>
                    <span>
                      {detail.service_point?.service_point_code
                        ? `Service point ${detail.service_point.service_point_code}`
                        : "No linked service point"}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}
