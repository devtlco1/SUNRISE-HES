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

export function AccountsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [accounts, setAccounts] = useState<AccountListItem[]>([]);
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

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="section-heading">
        <div>
          <h2>Accounts</h2>
          <p className="muted">
            Compact account browse flow into a bounded account detail surface.
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

      {isLoadingAccounts ? <p className="muted">Loading accounts...</p> : null}

      <div className="meter-list">
        {!isLoadingAccounts && accounts.length === 0 ? (
          <p className="muted">No accounts available for the current query.</p>
        ) : null}

        {accounts.map((account) => (
          <Link
            key={account.id}
            className="meter-list-item"
            href={`/accounts/${account.id}`}
          >
            <div className="command-list-item-header">
              <strong>{account.account_number}</strong>
              <span className="status-pill">{account.status}</span>
            </div>
            <div className="command-list-item-meta">
              <span>Account ID {account.id}</span>
              <span>{account.billing_cycle ?? "No billing cycle"}</span>
            </div>
            <div className="command-list-item-meta">
              <span>{account.subscriber_display_name}</span>
              <span>
                {account.service_point_code
                  ? `Service point ${account.service_point_code}`
                  : "No linked service point"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>
                {account.primary_meter_serial_number
                  ? `Meter ${account.primary_meter_serial_number}`
                  : "No linked current meter"}
              </span>
              <span>{account.linked_meter_count} linked meter(s)</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
