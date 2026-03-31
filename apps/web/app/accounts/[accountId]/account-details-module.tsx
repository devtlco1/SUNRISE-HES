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

  return (
    <section className="panel">
      {detailError ? <p className="error-banner">{detailError}</p> : null}
      {isLoadingDetail ? <p className="muted">Loading account detail...</p> : null}

      {detail ? (
        <>
          <div className="section-heading">
            <div>
              <h2>{detail.account_number}</h2>
              <p className="muted">
                {detail.status} account with {detail.linked_meter_count} linked current meter(s).
              </p>
            </div>
            <span className="status-pill">{detail.status}</span>
          </div>

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
                <strong>{detail.subscriber.consumer_type}</strong>
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
                    <span className="status-pill">
                      {detail.service_point.premises_type ?? "premise"}
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
                    <span className="status-pill">{meter.current_status}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter ID {meter.id}</span>
                    <span>{meter.utility_meter_number ?? "No utility number"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Open existing meter detail</span>
                    <span>Current account linkage</span>
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
