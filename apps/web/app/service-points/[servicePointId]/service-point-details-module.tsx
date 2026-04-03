"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type ServicePointLinkedMeter = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  current_status: string;
  account_id: string | null;
  account_number: string | null;
};

type ServicePointLinkedSubscriber = {
  id: string;
  full_name: string;
  consumer_type: string;
  account_id: string | null;
  account_number: string | null;
  account_status: string | null;
};

type ServicePointDetail = {
  id: string;
  service_point_code: string;
  address_line: string | null;
  premises_type: string | null;
  is_active: boolean;
  latitude: number | null;
  longitude: number | null;
  linked_meter_count: number;
  linked_subscriber_count: number;
  linked_account_count: number;
  linked_meters: ServicePointLinkedMeter[];
  linked_subscribers: ServicePointLinkedSubscriber[];
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
    normalized.includes("commercial") ||
    normalized.includes("residential") ||
    normalized.includes("registered")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("closed") ||
    normalized.includes("disconnected")
  ) {
    return "danger";
  }
  if (normalized.includes("pending") || normalized.includes("review")) {
    return "warning";
  }
  return "neutral";
}

function formatCoordinates(latitude: number | null, longitude: number | null): string {
  if (latitude === null || longitude === null) {
    return "Not available";
  }
  return `${latitude}, ${longitude}`;
}

export function ServicePointDetailsModule({
  servicePointId,
  authorizedFetch,
}: {
  servicePointId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [detail, setDetail] = useState<ServicePointDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const loadDetail = useCallback(async () => {
    setIsLoadingDetail(true);
    setDetailError(null);

    try {
      const response = await authorizedFetch<ServicePointDetail>(
        `/api/v1/service-points/${servicePointId}`,
      );
      setDetail(response);
    } catch (error) {
      setDetail(null);
      setDetailError(
        error instanceof Error
          ? error.message
          : "Unable to load service point detail.",
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, [authorizedFetch, servicePointId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const primaryLinkedMeter = detail?.linked_meters[0] ?? null;
  const primaryLinkedSubscriber = detail?.linked_subscribers[0] ?? null;
  const workspaceCards = detail
    ? [
        {
          label: "Service point identity",
          value: detail.service_point_code,
          note: `${detail.is_active ? "Active" : "Inactive"} • ${detail.id}`,
        },
        {
          label: "Premise context",
          value: formatStatusLabel(detail.premises_type ?? "premise"),
          note: detail.address_line ?? "No address summary recorded",
        },
        {
          label: "Subscriber context",
          value: primaryLinkedSubscriber?.full_name ?? "No linked subscriber",
          note: primaryLinkedSubscriber
            ? `${formatStatusLabel(primaryLinkedSubscriber.consumer_type)} • ${primaryLinkedSubscriber.account_number ?? "No linked account"}`
            : "No active subscriber linkage recorded",
        },
        {
          label: "Account context",
          value:
            primaryLinkedSubscriber?.account_number ??
            `${detail.linked_account_count} linked account(s)`,
          note: primaryLinkedSubscriber?.account_status
            ? formatStatusLabel(primaryLinkedSubscriber.account_status)
            : "No linked account status summary",
        },
        {
          label: "Primary meter",
          value: primaryLinkedMeter?.serial_number ?? "No linked meter",
          note: primaryLinkedMeter
            ? `${formatStatusLabel(primaryLinkedMeter.current_status)} • ${primaryLinkedMeter.utility_meter_number ?? "No utility number"}`
            : "No active meter linkage recorded",
        },
        {
          label: "Coordinates",
          value: formatCoordinates(detail.latitude, detail.longitude),
          note:
            detail.latitude !== null && detail.longitude !== null
              ? "GIS/location coordinates recorded"
              : "No coordinate visibility recorded",
        },
      ]
    : [];

  return (
    <section className="panel">
      {detailError ? <p className="error-banner">{detailError}</p> : null}
      {isLoadingDetail ? <p className="muted">Loading service point detail...</p> : null}

      {detail ? (
        <>
          <section className="subpanel service-points-overview-panel">
            <section className="service-point-detail-hero">
              <div className="service-point-detail-title-row">
                <div>
                  <p className="eyebrow">Service Point Detail</p>
                  <h2>{detail.service_point_code}</h2>
                  <p className="muted">
                    {formatStatusLabel(detail.premises_type ?? "premise")} with{" "}
                    {detail.linked_meter_count} linked meter(s),{" "}
                    {detail.linked_subscriber_count} linked subscriber(s), and{" "}
                    {detail.linked_account_count} linked account(s).
                  </p>
                </div>
                <span
                  className={`status-pill ${buildStatusTone(
                    detail.is_active ? "active" : "inactive",
                  )}`}
                >
                  {detail.is_active ? "Active" : "Inactive"}
                </span>
              </div>

              <div className="command-list-item-badges">
                <span className="artifact-pill">Service point {detail.id}</span>
                <span className="artifact-pill">
                  {detail.address_line ?? "No address summary"}
                </span>
                <span className="artifact-pill">
                  {detail.latitude !== null && detail.longitude !== null
                    ? formatCoordinates(detail.latitude, detail.longitude)
                    : "No coordinate summary"}
                </span>
              </div>

              <div className="artifact-row">
                {primaryLinkedSubscriber ? (
                  <Link
                    className="primary-button"
                    href={`/subscribers/${primaryLinkedSubscriber.id}`}
                  >
                    Open linked subscriber detail
                  </Link>
                ) : null}
                {primaryLinkedSubscriber?.account_id ? (
                  <Link
                    className="secondary-button"
                    href={`/accounts/${primaryLinkedSubscriber.account_id}`}
                  >
                    Open linked account detail
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

            <div className="service-points-overview-grid">
              <div className="stat-card service-points-overview-card">
                <span className="stat-label">Premises type</span>
                <strong>{formatStatusLabel(detail.premises_type ?? "premise")}</strong>
              </div>
              <div className="stat-card service-points-overview-card">
                <span className="stat-label">Linked meters</span>
                <strong>{detail.linked_meter_count}</strong>
              </div>
              <div className="stat-card service-points-overview-card">
                <span className="stat-label">Linked subscribers</span>
                <strong>{detail.linked_subscriber_count}</strong>
              </div>
              <div className="stat-card service-points-overview-card">
                <span className="stat-label">Linked accounts</span>
                <strong>{detail.linked_account_count}</strong>
              </div>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Service point workspace</h3>
                <p className="muted">
                  Dense operational and commercial summary for the selected service point.
                </p>
              </div>
            </div>
            <div className="service-points-overview-grid">
              {workspaceCards.map((card) => (
                <div key={card.label} className="stat-card service-points-overview-card">
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
                <h3>Location summary</h3>
                <p className="muted">
                  Compact address and coordinate visibility for the selected service point.
                </p>
              </div>
            </div>
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Service point ID</span>
                <strong>{detail.id}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Address</span>
                <strong>{detail.address_line ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Premises type</span>
                <strong>{formatStatusLabel(detail.premises_type ?? "Not available")}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Latitude</span>
                <strong>{detail.latitude ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Longitude</span>
                <strong>{detail.longitude ?? "Not available"}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Linked accounts</span>
                <strong>{detail.linked_account_count}</strong>
              </div>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked meters</h3>
                <p className="muted">
                  Bounded meter context for this service point.
                </p>
              </div>
              <span className="artifact-pill">{detail.linked_meters.length} meter(s)</span>
            </div>
            <div className="meter-list">
              {detail.linked_meters.length === 0 ? (
                <p className="muted">No meters linked to this service point.</p>
              ) : null}
              {detail.linked_meters.map((meter) => (
                <div key={meter.id} className="meter-list-item">
                  <div className="command-list-item-header">
                    <Link href={`/meters/${meter.id}`}>
                      <strong>{meter.serial_number}</strong>
                    </Link>
                    <span className={`status-pill ${buildStatusTone(meter.current_status)}`}>
                      {formatStatusLabel(meter.current_status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {meter.utility_meter_number ?? "No utility number"}
                    </span>
                    <span className="artifact-pill">
                      {meter.account_number
                        ? `Account ${meter.account_number}`
                        : "No linked account summary"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter ID {meter.id}</span>
                    <span>Open existing meter detail</span>
                  </div>
                  <div className="artifact-row">
                    <Link className="secondary-button" href={`/meters/${meter.id}`}>
                      Open meter detail
                    </Link>
                    {meter.account_id ? (
                      <Link
                        className="secondary-button"
                        href={`/accounts/${meter.account_id}`}
                      >
                        Open linked account detail
                      </Link>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked subscribers</h3>
                <p className="muted">
                  Bounded subscriber visibility for the selected service point.
                </p>
              </div>
              <span className="artifact-pill">
                {detail.linked_subscribers.length} subscriber(s)
              </span>
            </div>
            <div className="meter-list">
              {detail.linked_subscribers.length === 0 ? (
                <p className="muted">No subscribers linked to this service point.</p>
              ) : null}
              {detail.linked_subscribers.map((subscriber) => (
                <div key={subscriber.id} className="meter-list-item">
                  <div className="command-list-item-header">
                    <Link href={`/subscribers/${subscriber.id}`}>
                      <strong>{subscriber.full_name}</strong>
                    </Link>
                    <span
                      className={`status-pill ${buildStatusTone(
                        subscriber.account_status ?? subscriber.consumer_type,
                      )}`}
                    >
                      {formatStatusLabel(
                        subscriber.account_status ?? subscriber.consumer_type,
                      )}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {formatStatusLabel(subscriber.consumer_type)}
                    </span>
                    <span className="artifact-pill">
                      {subscriber.account_number
                        ? `Account ${subscriber.account_number}`
                        : "No linked account summary"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Subscriber ID {subscriber.id}</span>
                    <span>Open existing subscriber detail</span>
                  </div>
                  <div className="artifact-row">
                    <Link className="secondary-button" href={`/subscribers/${subscriber.id}`}>
                      Open subscriber detail
                    </Link>
                    {subscriber.account_id ? (
                      <Link
                        className="secondary-button"
                        href={`/accounts/${subscriber.account_id}`}
                      >
                        Open linked account detail
                      </Link>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}
