"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type SubscriberListItem = {
  id: string;
  full_name: string;
  consumer_type: string;
  external_ref: string | null;
  national_id: string | null;
  primary_account_number: string | null;
  account_status_summary: string | null;
  active_account_count: number;
  linked_meter_count: number;
  primary_service_point_code: string | null;
};

type SubscriberListResponse = {
  total: number;
  items: SubscriberListItem[];
};

export function SubscribersModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [subscribers, setSubscribers] = useState<SubscriberListItem[]>([]);
  const [totalSubscribers, setTotalSubscribers] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingSubscribers, setIsLoadingSubscribers] = useState(false);

  const loadSubscribers = useCallback(async () => {
    setIsLoadingSubscribers(true);
    setPageError(null);

    try {
      const params = new URLSearchParams({
        offset: "0",
        limit: "20",
      });
      if (appliedSearch.trim()) {
        params.set("search", appliedSearch.trim());
      }

      const response = await authorizedFetch<SubscriberListResponse>(
        `/api/v1/consumers?${params.toString()}`,
      );
      setSubscribers(response.items);
      setTotalSubscribers(response.total);
    } catch (error) {
      setSubscribers([]);
      setTotalSubscribers(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load subscribers.",
      );
    } finally {
      setIsLoadingSubscribers(false);
    }
  }, [appliedSearch, authorizedFetch]);

  useEffect(() => {
    void loadSubscribers();
  }, [loadSubscribers]);

  const statusSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `${totalSubscribers} matching subscribers`;
    }
    return `${totalSubscribers} recent subscribers`;
  }, [appliedSearch, totalSubscribers]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="section-heading">
        <div>
          <h2>Subscribers / Consumers</h2>
          <p className="muted">
            Compact operational browse flow into a bounded subscriber detail view.
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
            placeholder="Name, external reference, or national ID"
          />
        </label>
        <button
          className="primary-button"
          disabled={isLoadingSubscribers}
          type="submit"
        >
          {isLoadingSubscribers ? "Loading..." : "Load subscribers"}
        </button>
      </form>

      {isLoadingSubscribers ? (
        <p className="muted">Loading subscribers...</p>
      ) : null}

      <div className="meter-list">
        {!isLoadingSubscribers && subscribers.length === 0 ? (
          <p className="muted">No subscribers available for the current query.</p>
        ) : null}

        {subscribers.map((subscriber) => (
          <Link
            key={subscriber.id}
            className="meter-list-item"
            href={`/subscribers/${subscriber.id}`}
          >
            <div className="command-list-item-header">
              <strong>{subscriber.full_name}</strong>
              <span className="status-pill">
                {subscriber.account_status_summary ?? "unassigned"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>Consumer ID {subscriber.id}</span>
              <span>
                {subscriber.primary_account_number
                  ? `Account ${subscriber.primary_account_number}`
                  : "No linked account"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>
                {subscriber.external_ref ??
                  subscriber.national_id ??
                  "No key external identifier"}
              </span>
              <span>
                {subscriber.primary_service_point_code
                  ? `Service point ${subscriber.primary_service_point_code}`
                  : subscriber.consumer_type}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>{subscriber.linked_meter_count} linked meter(s)</span>
              <span>{subscriber.active_account_count} active account(s)</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
