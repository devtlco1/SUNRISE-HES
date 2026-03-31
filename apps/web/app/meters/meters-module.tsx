"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type MeterItem = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  manufacturer_code: string;
  meter_model_code: string;
  communication_profile_code: string | null;
  meter_profile_code: string | null;
  current_status: string;
  last_seen_at: string | null;
  is_active: boolean;
};

type MeterListResponse = {
  total: number;
  items: MeterItem[];
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function MetersModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [meters, setMeters] = useState<MeterItem[]>([]);
  const [totalMeters, setTotalMeters] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingMeters, setIsLoadingMeters] = useState(false);

  const loadMeters = useCallback(async () => {
    setIsLoadingMeters(true);
    setPageError(null);

    try {
      const params = new URLSearchParams({
        offset: "0",
        limit: "20",
      });
      if (appliedSearch.trim()) {
        params.set("search", appliedSearch.trim());
      }

      const response = await authorizedFetch<MeterListResponse>(
        `/api/v1/meters?${params.toString()}`,
      );
      setMeters(response.items);
      setTotalMeters(response.total);
    } catch (error) {
      setMeters([]);
      setTotalMeters(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load meters.",
      );
    } finally {
      setIsLoadingMeters(false);
    }
  }, [appliedSearch, authorizedFetch]);

  useEffect(() => {
    void loadMeters();
  }, [loadMeters]);

  const statusSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `${totalMeters} matching meters`;
    }
    return `${totalMeters} recent meters`;
  }, [appliedSearch, totalMeters]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="section-heading">
        <div>
          <h2>Meters</h2>
          <p className="muted">
            Compact operational meter browse flow into the existing meter details
            page.
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
            placeholder="Serial, utility meter number, or badge"
          />
        </label>
        <button className="primary-button" disabled={isLoadingMeters} type="submit">
          {isLoadingMeters ? "Loading..." : "Load meters"}
        </button>
      </form>

      {isLoadingMeters ? <p className="muted">Loading meters...</p> : null}

      <div className="meter-list">
        {!isLoadingMeters && meters.length === 0 ? (
          <p className="muted">No meters available for the current query.</p>
        ) : null}

        {meters.map((meter) => (
          <Link
            key={meter.id}
            className="meter-list-item"
            href={`/meters/${meter.id}`}
          >
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
                {meter.manufacturer_code} / {meter.meter_model_code}
              </span>
              <span>
                {meter.communication_profile_code ??
                  meter.meter_profile_code ??
                  "No active profile summary"}
              </span>
            </div>
            <div className="command-list-item-meta">
              <span>{meter.is_active ? "Active meter" : "Inactive meter"}</span>
              <span>Last seen {formatDateTime(meter.last_seen_at)}</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
