"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type ServicePointListItem = {
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
  primary_meter_serial_number: string | null;
  primary_subscriber_display_name: string | null;
};

type ServicePointListResponse = {
  total: number;
  items: ServicePointListItem[];
};

export function ServicePointsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [items, setItems] = useState<ServicePointListItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingItems, setIsLoadingItems] = useState(false);

  const loadServicePoints = useCallback(async () => {
    setIsLoadingItems(true);
    setPageError(null);

    try {
      const params = new URLSearchParams({
        offset: "0",
        limit: "20",
      });
      if (appliedSearch.trim()) {
        params.set("search", appliedSearch.trim());
      }

      const response = await authorizedFetch<ServicePointListResponse>(
        `/api/v1/service-points?${params.toString()}`,
      );
      setItems(response.items);
      setTotalItems(response.total);
    } catch (error) {
      setItems([]);
      setTotalItems(0);
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load service points.",
      );
    } finally {
      setIsLoadingItems(false);
    }
  }, [appliedSearch, authorizedFetch]);

  useEffect(() => {
    void loadServicePoints();
  }, [loadServicePoints]);

  const statusSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `${totalItems} matching service points`;
    }
    return `${totalItems} recent service points`;
  }, [appliedSearch, totalItems]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="section-heading">
        <div>
          <h2>Service Points / Premises</h2>
          <p className="muted">
            Compact service-point browse flow into a bounded premise detail surface.
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
            placeholder="Service point code, address, or premises type"
          />
        </label>
        <button className="primary-button" disabled={isLoadingItems} type="submit">
          {isLoadingItems ? "Loading..." : "Load service points"}
        </button>
      </form>

      {isLoadingItems ? <p className="muted">Loading service points...</p> : null}

      <div className="meter-list">
        {!isLoadingItems && items.length === 0 ? (
          <p className="muted">No service points available for the current query.</p>
        ) : null}

        {items.map((item) => (
          <Link
            key={item.id}
            className="meter-list-item"
            href={`/service-points/${item.id}`}
          >
            <div className="command-list-item-header">
              <strong>{item.service_point_code}</strong>
              <span className="status-pill">
                {item.is_active ? "active" : "inactive"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>Service point ID {item.id}</span>
              <span>{item.premises_type ?? "No premises type"}</span>
            </div>
            <div className="command-list-item-meta">
              <span>{item.address_line ?? "No address summary"}</span>
              <span>
                {item.primary_meter_serial_number
                  ? `Meter ${item.primary_meter_serial_number}`
                  : "No linked meter"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>
                {item.primary_subscriber_display_name ??
                  "No linked subscriber"}
              </span>
              <span>
                {item.latitude !== null && item.longitude !== null
                  ? `${item.latitude}, ${item.longitude}`
                  : "No coordinate summary"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>{item.linked_meter_count} linked meter(s)</span>
              <span>{item.linked_subscriber_count} linked subscriber(s)</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
