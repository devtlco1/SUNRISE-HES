"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type TransformerSubstationListItem = {
  id: string;
  code: string;
  name: string;
  status: string;
  feeder_code: string;
  substation_id: string;
  substation_code: string;
  substation_name: string;
  linked_meter_count: number;
  linked_service_point_count: number;
  primary_meter_serial_number: string | null;
  primary_service_point_code: string | null;
  location_hint: string | null;
};

type TransformerSubstationListResponse = {
  total: number;
  items: TransformerSubstationListItem[];
};

export function TransformersSubstationsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [items, setItems] = useState<TransformerSubstationListItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingItems, setIsLoadingItems] = useState(false);

  const loadItems = useCallback(async () => {
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

      const response = await authorizedFetch<TransformerSubstationListResponse>(
        `/api/v1/transformers-substations?${params.toString()}`,
      );
      setItems(response.items);
      setTotalItems(response.total);
    } catch (error) {
      setItems([]);
      setTotalItems(0);
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load transformer and substation visibility.",
      );
    } finally {
      setIsLoadingItems(false);
    }
  }, [appliedSearch, authorizedFetch]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const statusSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `${totalItems} matching infrastructure item(s)`;
    }
    return `${totalItems} infrastructure item(s)`;
  }, [appliedSearch, totalItems]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="section-heading">
        <div>
          <h2>Transformers / Substations</h2>
          <p className="muted">
            Compact read-only infrastructure browse flow into bounded transformer and
            parent substation context.
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
            placeholder="Transformer, feeder, substation, sector, or region"
          />
        </label>
        <button className="primary-button" disabled={isLoadingItems} type="submit">
          {isLoadingItems ? "Loading..." : "Load infrastructure"}
        </button>
      </form>

      {isLoadingItems ? (
        <p className="muted">Loading transformer and substation visibility...</p>
      ) : null}

      <div className="meter-list">
        {!isLoadingItems && items.length === 0 ? (
          <p className="muted">
            No transformer or substation visibility is available for the current query.
          </p>
        ) : null}

        {items.map((item) => (
          <Link
            key={item.id}
            className="meter-list-item"
            href={`/transformers-substations/${item.id}`}
          >
            <div className="command-list-item-header">
              <strong>
                {item.code} · {item.name}
              </strong>
              <span className="status-pill">{item.status}</span>
            </div>
            <div className="command-list-item-meta">
              <span>Transformer ID {item.id}</span>
              <span>Feeder {item.feeder_code}</span>
            </div>
            <div className="command-list-item-meta">
              <span>
                Substation {item.substation_code} · {item.substation_name}
              </span>
              <span>{item.location_hint ?? "No location hint"}</span>
            </div>
            <div className="command-list-item-meta">
              <span>
                {item.primary_meter_serial_number
                  ? `Meter ${item.primary_meter_serial_number}`
                  : "No linked meter"}
              </span>
              <span>
                {item.primary_service_point_code
                  ? `Service point ${item.primary_service_point_code}`
                  : "No linked service point"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>{item.linked_meter_count} linked meter(s)</span>
              <span>{item.linked_service_point_count} linked service point(s)</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
