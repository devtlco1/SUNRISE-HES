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

  return (
    <section className="panel">
      {detailError ? <p className="error-banner">{detailError}</p> : null}
      {isLoadingDetail ? <p className="muted">Loading service point detail...</p> : null}

      {detail ? (
        <>
          <div className="section-heading">
            <div>
              <h2>{detail.service_point_code}</h2>
              <p className="muted">
                {detail.premises_type ?? "premise"} with {detail.linked_meter_count} linked
                meter(s), {detail.linked_subscriber_count} linked subscriber(s), and{" "}
                {detail.linked_account_count} linked account(s).
              </p>
            </div>
            <span className="status-pill">
              {detail.is_active ? "active" : "inactive"}
            </span>
          </div>

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
                <strong>{detail.premises_type ?? "Not available"}</strong>
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
                <Link key={meter.id} className="meter-list-item" href={`/meters/${meter.id}`}>
                  <div className="command-list-item-header">
                    <strong>{meter.serial_number}</strong>
                    <span className="status-pill">{meter.current_status}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter ID {meter.id}</span>
                    <span>{meter.utility_meter_number ?? "No utility number"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {meter.account_number
                        ? `Account ${meter.account_number}`
                        : "No linked account summary"}
                    </span>
                    <span>Open existing meter detail</span>
                  </div>
                </Link>
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
                <Link
                  key={subscriber.id}
                  className="meter-list-item"
                  href={`/subscribers/${subscriber.id}`}
                >
                  <div className="command-list-item-header">
                    <strong>{subscriber.full_name}</strong>
                    <span className="status-pill">
                      {subscriber.account_status ?? subscriber.consumer_type}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Subscriber ID {subscriber.id}</span>
                    <span>{subscriber.consumer_type}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {subscriber.account_number
                        ? `Account ${subscriber.account_number}`
                        : "No linked account summary"}
                    </span>
                    <span>Open existing subscriber detail</span>
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
