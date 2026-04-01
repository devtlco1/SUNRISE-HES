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
  const [selectedMeterIds, setSelectedMeterIds] = useState<string[]>([]);
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
      setSelectedMeterIds((currentSelectedMeterIds) =>
        currentSelectedMeterIds.filter((meterId) =>
          response.items.some((item) => item.id === meterId),
        ),
      );
    } catch (error) {
      setMeters([]);
      setTotalMeters(0);
      setSelectedMeterIds([]);
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

  const visibleScopeSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `Visible result set is limited to meters matching "${appliedSearch.trim()}". Select visible adds only this filtered list to the bulk handoff.`;
    }

    return "Visible result set includes every meter currently shown in this list. Select visible adds only the meters shown here to the bulk handoff.";
  }, [appliedSearch]);

  const selectedMeters = useMemo(
    () => meters.filter((meter) => selectedMeterIds.includes(meter.id)),
    [meters, selectedMeterIds],
  );

  const selectedMetersCommandsHref = useMemo(() => {
    if (selectedMeterIds.length === 0) {
      return "/commands";
    }

    const params = new URLSearchParams({
      meterIds: selectedMeterIds.join(","),
    });
    return `/commands?${params.toString()}`;
  }, [selectedMeterIds]);

  const registryCards = useMemo(
    () => [
      {
        label: "Meters in current result",
        value: String(totalMeters),
      },
      {
        label: "Active inventory items",
        value: String(meters.filter((meter) => meter.is_active).length),
      },
      {
        label: "Recent signal visible",
        value: String(meters.filter((meter) => meter.last_seen_at !== null).length),
      },
      {
        label: "Communication profile present",
        value: String(
          meters.filter((meter) => meter.communication_profile_code !== null).length,
        ),
      },
    ],
    [meters, totalMeters],
  );

  const toggleMeterSelection = useCallback((meterId: string) => {
    setSelectedMeterIds((currentSelectedMeterIds) =>
      currentSelectedMeterIds.includes(meterId)
        ? currentSelectedMeterIds.filter((item) => item !== meterId)
        : [...currentSelectedMeterIds, meterId],
    );
  }, []);

  const selectVisibleMeters = useCallback(() => {
    setSelectedMeterIds(meters.map((meter) => meter.id));
  }, [meters]);

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

      <section className="subpanel">
        <div className="section-heading">
          <div>
            <h3>Registry snapshot</h3>
            <p className="muted">
              Productized inventory summary for the current meter result set.
            </p>
          </div>
        </div>
        <div className="meter-summary-grid">
          {registryCards.map((card) => (
            <div key={card.label} className="stat-card">
              <span className="stat-label">{card.label}</span>
              <strong>{card.value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="subpanel">
        <div className="section-heading">
          <div>
            <h3>Meter inventory</h3>
            <p className="muted">
              Refined inventory rows aligned with the adopted operational shell.
            </p>
          </div>
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

        <div className="commands-selection-summary">
          <span className="artifact-pill">
            {selectedMeterIds.length} selected target
            {selectedMeterIds.length === 1 ? "" : "s"} for bulk handoff
          </span>
          <span className="artifact-pill">
            {meters.length} meter
            {meters.length === 1 ? "" : "s"} visible in current result set
          </span>
          <span className="artifact-pill">
            Bulk handoff uses the current visible result set only
          </span>
        </div>

        <p className="muted">{visibleScopeSummary}</p>

        <div className="artifact-row">
          <button
            className="secondary-button"
            disabled={meters.length === 0}
            onClick={selectVisibleMeters}
            type="button"
          >
            Select visible
          </button>
          <button
            className="secondary-button"
            disabled={selectedMeterIds.length === 0}
            onClick={() => setSelectedMeterIds([])}
            type="button"
          >
            Clear selection
          </button>
          {selectedMeterIds.length > 0 ? (
            <Link className="primary-button" href={selectedMetersCommandsHref}>
              Open bulk commands
            </Link>
          ) : (
            <button className="primary-button" disabled type="button">
              Open bulk commands
            </button>
          )}
        </div>

        {selectedMeters.length > 0 ? (
          <div className="artifact-row">
            {selectedMeters.map((meter) => (
              <span key={meter.id} className="artifact-pill">
                {meter.serial_number}
              </span>
            ))}
          </div>
        ) : null}

        {isLoadingMeters ? <p className="muted">Loading meters...</p> : null}

        <div className="meter-list">
          {!isLoadingMeters && meters.length === 0 ? (
            <p className="muted">No meters available for the current query.</p>
          ) : null}

          {meters.map((meter) => {
            const isSelected = selectedMeterIds.includes(meter.id);
            return (
              <article
                key={meter.id}
                className={`meter-list-item meter-registry-item${isSelected ? " selected" : ""}`}
              >
                <div className="meter-registry-row">
                <div className="meter-registry-primary">
                  <div className="command-list-item-header">
                    <strong>{meter.serial_number}</strong>
                    <span className="status-pill">{meter.current_status}</span>
                  </div>
                  <div className="meter-registry-badges">
                    <span className="artifact-pill">
                      {meter.is_active ? "Active inventory" : "Inactive inventory"}
                    </span>
                    <span className="artifact-pill">
                      {meter.communication_profile_code
                        ? "Connected profile"
                        : "Profile pending"}
                    </span>
                  </div>
                </div>

                <div className="meter-registry-metrics">
                  <div className="meter-registry-metric">
                    <span className="stat-label">Meter ID</span>
                    <strong>{meter.id}</strong>
                  </div>
                  <div className="meter-registry-metric">
                    <span className="stat-label">Utility number</span>
                    <strong>{meter.utility_meter_number ?? "No utility number"}</strong>
                  </div>
                  <div className="meter-registry-metric">
                    <span className="stat-label">Catalog</span>
                    <strong>
                      {meter.manufacturer_code} / {meter.meter_model_code}
                    </strong>
                  </div>
                  <div className="meter-registry-metric">
                    <span className="stat-label">Operational profile</span>
                    <strong>
                      {meter.communication_profile_code ??
                        meter.meter_profile_code ??
                        "No active profile summary"}
                    </strong>
                  </div>
                  <div className="meter-registry-metric">
                    <span className="stat-label">Last seen</span>
                    <strong>{formatDateTime(meter.last_seen_at)}</strong>
                  </div>
                </div>
                </div>

                <div className="artifact-row">
                  <Link className="secondary-button" href={`/meters/${meter.id}`}>
                    Open meter detail
                  </Link>
                  <label className="checkbox-option">
                    <input
                      checked={isSelected}
                      onChange={() => toggleMeterSelection(meter.id)}
                      type="checkbox"
                    />
                    Include in bulk target scope
                  </label>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </section>
  );
}
