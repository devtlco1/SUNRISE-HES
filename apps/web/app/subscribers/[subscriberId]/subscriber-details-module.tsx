"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type SubscriberAccount = {
  id: string;
  account_number: string;
  status: string;
  billing_cycle: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
  current_meter_count: number;
};

type SubscriberLinkedMeter = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  current_status: string;
  account_id: string | null;
  account_number: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
};

type SubscriberDetail = {
  id: string;
  full_name: string;
  consumer_type: string;
  external_ref: string | null;
  national_id: string | null;
  phone_number: string | null;
  email: string | null;
  account_status_summary: string | null;
  active_account_count: number;
  linked_meter_count: number;
  current_operational_meter: SubscriberLinkedMeter | null;
  accounts: SubscriberAccount[];
  linked_meters: SubscriberLinkedMeter[];
};

export function SubscriberDetailsModule({
  subscriberId,
  authorizedFetch,
}: {
  subscriberId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [detail, setDetail] = useState<SubscriberDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const loadDetail = useCallback(async () => {
    setIsLoadingDetail(true);
    setDetailError(null);

    try {
      const response = await authorizedFetch<SubscriberDetail>(
        `/api/v1/consumers/${subscriberId}`,
      );
      setDetail(response);
    } catch (error) {
      setDetail(null);
      setDetailError(
        error instanceof Error
          ? error.message
          : "Unable to load subscriber detail.",
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, [authorizedFetch, subscriberId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  return (
    <section className="panel">
      {detailError ? <p className="error-banner">{detailError}</p> : null}
      {isLoadingDetail ? <p className="muted">Loading subscriber detail...</p> : null}

      {detail ? (
        <>
          <div className="section-heading">
            <div>
              <h2>{detail.full_name}</h2>
              <p className="muted">
                {detail.consumer_type} subscriber with {detail.active_account_count} active
                account(s) and {detail.linked_meter_count} linked meter(s).
              </p>
            </div>
            <span className="status-pill">
              {detail.account_status_summary ?? "unassigned"}
            </span>
          </div>

          <section className="subpanel">
            <h3>Operational identifiers</h3>
            <div className="command-list-item-meta">
              <span>Consumer ID {detail.id}</span>
              <span>{detail.external_ref ?? "No external reference"}</span>
            </div>
            <div className="command-list-item-meta">
              <span>{detail.national_id ?? "No national ID"}</span>
              <span>{detail.phone_number ?? detail.email ?? "No contact summary"}</span>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Current operational meter</h3>
                <p className="muted">
                  Compact reverse linkage into the bounded meter detail surface.
                </p>
              </div>
            </div>
            {detail.current_operational_meter ? (
              <div className="detail-stack">
                <div className="meter-summary-grid">
                  <div className="stat-card">
                    <span className="stat-label">Meter</span>
                    <strong>{detail.current_operational_meter.serial_number}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Meter ID</span>
                    <strong>{detail.current_operational_meter.id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Utility meter number</span>
                    <strong>
                      {detail.current_operational_meter.utility_meter_number ??
                        "Not available"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Meter status</span>
                    <strong>{detail.current_operational_meter.current_status}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Account</span>
                    <strong>
                      {detail.current_operational_meter.account_number ??
                        "No linked account summary"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Service point</span>
                    <strong>
                      {detail.current_operational_meter.service_point_code ??
                        "No linked service point"}
                    </strong>
                  </div>
                </div>
                <div className="artifact-row">
                  <Link
                    className="primary-button"
                    href={`/meters/${detail.current_operational_meter.id}`}
                  >
                    Open meter detail
                  </Link>
                </div>
              </div>
            ) : (
              <p className="muted">
                No current operational meter available for this subscriber.
              </p>
            )}
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Accounts</h3>
                <p className="muted">Bounded account visibility for the selected subscriber.</p>
              </div>
              <span className="artifact-pill">{detail.accounts.length} account(s)</span>
            </div>
            <div className="meter-list">
              {detail.accounts.length === 0 ? (
                <p className="muted">No accounts linked to this subscriber.</p>
              ) : null}
              {detail.accounts.map((account) => (
                <div key={account.id} className="meter-list-item">
                  <div className="command-list-item-header">
                    <strong>{account.account_number}</strong>
                    <span className="status-pill">{account.status}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Account ID {account.id}</span>
                    <span>{account.billing_cycle ?? "No billing cycle"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {account.service_point_code
                        ? `Service point ${account.service_point_code}`
                        : "No linked service point"}
                    </span>
                    <span>{account.current_meter_count} current meter(s)</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked meters</h3>
                <p className="muted">Current operational meter linkage for this subscriber.</p>
              </div>
              <span className="artifact-pill">
                {detail.linked_meters.length} meter(s)
              </span>
            </div>
            <div className="meter-list">
              {detail.linked_meters.length === 0 ? (
                <p className="muted">No meters linked to this subscriber.</p>
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
                    <span>
                      {meter.service_point_code
                        ? `Service point ${meter.service_point_code}`
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
