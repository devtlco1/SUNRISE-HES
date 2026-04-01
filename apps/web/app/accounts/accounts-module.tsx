"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type AccountListItem = {
  id: string;
  account_number: string;
  status: string;
  billing_cycle: string | null;
  subscriber_id: string;
  subscriber_display_name: string;
  service_point_id: string | null;
  service_point_code: string | null;
  linked_meter_count: number;
  primary_meter_serial_number: string | null;
};

type AccountListResponse = {
  total: number;
  items: AccountListItem[];
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
    normalized.includes("linked")
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

export function AccountsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [accounts, setAccounts] = useState<AccountListItem[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [totalAccounts, setTotalAccounts] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);

  const loadAccounts = useCallback(async () => {
    setIsLoadingAccounts(true);
    setPageError(null);

    try {
      const params = new URLSearchParams({
        offset: "0",
        limit: "20",
      });
      if (appliedSearch.trim()) {
        params.set("search", appliedSearch.trim());
      }

      const response = await authorizedFetch<AccountListResponse>(
        `/api/v1/accounts?${params.toString()}`,
      );
      setAccounts(response.items);
      setTotalAccounts(response.total);
    } catch (error) {
      setAccounts([]);
      setTotalAccounts(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load accounts.",
      );
    } finally {
      setIsLoadingAccounts(false);
    }
  }, [appliedSearch, authorizedFetch]);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  const statusSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `${totalAccounts} matching accounts`;
    }
    return `${totalAccounts} recent accounts`;
  }, [appliedSearch, totalAccounts]);

  const overviewCards = useMemo(() => {
    const linkedMeters = accounts.reduce(
      (total, account) => total + account.linked_meter_count,
      0,
    );
    const withServicePoint = accounts.filter(
      (account) => account.service_point_code !== null,
    ).length;
    const withPrimaryMeter = accounts.filter(
      (account) => account.primary_meter_serial_number !== null,
    ).length;

    return [
      {
        label: "Accounts in current view",
        value: String(accounts.length),
      },
      {
        label: "Linked meters represented",
        value: String(linkedMeters),
      },
      {
        label: "Service points visible",
        value: String(withServicePoint),
      },
      {
        label: "Primary meters visible",
        value: String(withPrimaryMeter),
      },
    ];
  }, [accounts]);

  useEffect(() => {
    setSelectedAccountId((currentSelectedAccountId) => {
      if (currentSelectedAccountId && accounts.some((account) => account.id === currentSelectedAccountId)) {
        return currentSelectedAccountId;
      }
      return accounts[0]?.id ?? null;
    });
  }, [accounts]);

  const selectedAccount = useMemo(
    () => accounts.find((account) => account.id === selectedAccountId) ?? accounts[0] ?? null,
    [accounts, selectedAccountId],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel accounts-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Account operations center</h2>
              <p className="muted">
                Bounded visibility into account identity, subscriber linkage, service
                context, and current operational meters.
              </p>
            </div>
            <span className="artifact-pill">{statusSummary}</span>
          </div>

          <form
            className="inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              setAppliedSearch(searchDraft);
            }}
          >
            <label className="field">
              <span>Search</span>
              <input
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                placeholder="Account number, subscriber, status, or billing cycle"
              />
            </label>
            <button className="primary-button" disabled={isLoadingAccounts} type="submit">
              {isLoadingAccounts ? "Loading..." : "Load accounts"}
            </button>
          </form>

          {isLoadingAccounts ? (
            <p className="muted">Loading accounts...</p>
          ) : (
            <div className="accounts-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card accounts-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="accounts-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Account list</h2>
                <p className="muted">
                  Browse the existing account surface and keep direct drill-down into
                  bounded detail routes.
                </p>
              </div>
            </div>

            <div className="meter-list">
              {!isLoadingAccounts && accounts.length === 0 ? (
                <p className="muted">No accounts available for the current query.</p>
              ) : null}

              {accounts.map((account) => (
                <div
                  key={account.id}
                  className={`meter-list-item account-list-item${
                    selectedAccount?.id === account.id ? " selected" : ""
                  }`}
                >
                  <div className="command-list-item-header">
                    <strong>{account.account_number}</strong>
                    <span className={`status-pill ${buildStatusTone(account.status)}`}>
                      {formatStatusLabel(account.status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {account.billing_cycle ?? "No billing cycle"}
                    </span>
                    <span className="artifact-pill">{account.subscriber_display_name}</span>
                    <span className="artifact-pill">
                      {account.service_point_code
                        ? `Service point ${account.service_point_code}`
                        : "No linked service point"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Account ID {account.id}</span>
                    <span>Subscriber {account.subscriber_id}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {account.primary_meter_serial_number
                        ? `Meter ${account.primary_meter_serial_number}`
                        : "No linked current meter"}
                    </span>
                    <span>{account.linked_meter_count} linked meter(s)</span>
                  </div>
                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedAccountId(account.id)}
                      type="button"
                    >
                      Inspect summary
                    </button>
                    <Link className="secondary-button" href={`/accounts/${account.id}`}>
                      Open account detail
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Selected account summary</h2>
                <p className="muted">
                  Bounded inline review of subscriber, service-point, and meter linkage
                  before opening the existing account detail route.
                </p>
              </div>
            </div>

            {isLoadingAccounts ? (
              <p className="muted">Loading selected account summary...</p>
            ) : selectedAccount ? (
              <div className="detail-stack">
                <section className="account-detail-hero">
                  <div className="account-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Account</p>
                      <h3>{selectedAccount.account_number}</h3>
                      <p className="muted">
                        {formatStatusLabel(selectedAccount.status)} account linked to{" "}
                        {selectedAccount.subscriber_display_name} with{" "}
                        {selectedAccount.linked_meter_count} current meter(s).
                      </p>
                    </div>
                    <span className={`status-pill ${buildStatusTone(selectedAccount.status)}`}>
                      {formatStatusLabel(selectedAccount.status)}
                    </span>
                  </div>

                  <div className="command-list-item-badges">
                    <span className="artifact-pill">{selectedAccount.subscriber_display_name}</span>
                    <span className="artifact-pill">
                      {selectedAccount.billing_cycle ?? "No billing cycle"}
                    </span>
                    <span className="artifact-pill">
                      {selectedAccount.service_point_code
                        ? `Service point ${selectedAccount.service_point_code}`
                        : "No linked service point"}
                    </span>
                  </div>
                </section>

                <div className="detail-grid">
                  <div className="stat-card">
                    <span className="stat-label">Account ID</span>
                    <strong>{selectedAccount.id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Subscriber ID</span>
                    <strong>{selectedAccount.subscriber_id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Current primary meter</span>
                    <strong>{selectedAccount.primary_meter_serial_number ?? "Not available"}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Linked meters</span>
                    <strong>{selectedAccount.linked_meter_count}</strong>
                  </div>
                </div>

                <div className="artifact-row">
                  <Link className="secondary-button" href={`/accounts/${selectedAccount.id}`}>
                    Open account detail
                  </Link>
                </div>
              </div>
            ) : (
              <p className="muted">No account selected for bounded summary review.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
