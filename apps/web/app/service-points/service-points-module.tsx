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
    normalized.includes("commercial") ||
    normalized.includes("residential")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("disconnected") ||
    normalized.includes("closed")
  ) {
    return "danger";
  }
  if (normalized.includes("pending") || normalized.includes("review")) {
    return "warning";
  }
  return "neutral";
}

export function ServicePointsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [items, setItems] = useState<ServicePointListItem[]>([]);
  const [selectedServicePointId, setSelectedServicePointId] = useState<string | null>(null);
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

  const overviewCards = useMemo(() => {
    const linkedMeters = items.reduce((total, item) => total + item.linked_meter_count, 0);
    const linkedSubscribers = items.reduce(
      (total, item) => total + item.linked_subscriber_count,
      0,
    );
    const linkedAccounts = items.reduce(
      (total, item) => total + item.linked_account_count,
      0,
    );
    const mappedCoordinates = items.filter(
      (item) => item.latitude !== null && item.longitude !== null,
    ).length;

    return [
      { label: "Service points in current view", value: String(items.length) },
      { label: "Linked meters represented", value: String(linkedMeters) },
      { label: "Linked subscribers represented", value: String(linkedSubscribers) },
      { label: "Coordinate-ready premises", value: String(mappedCoordinates) },
      { label: "Linked accounts represented", value: String(linkedAccounts) },
    ];
  }, [items]);

  useEffect(() => {
    setSelectedServicePointId((currentSelectedServicePointId) => {
      if (
        currentSelectedServicePointId &&
        items.some((item) => item.id === currentSelectedServicePointId)
      ) {
        return currentSelectedServicePointId;
      }
      return items[0]?.id ?? null;
    });
  }, [items]);

  const selectedServicePoint = useMemo(
    () =>
      items.find((item) => item.id === selectedServicePointId) ?? items[0] ?? null,
    [items, selectedServicePointId],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel service-points-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Service point operations center</h2>
              <p className="muted">
                Bounded visibility into premise identity, address context, and linked
                subscriber, account, and meter surfaces.
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

          {isLoadingItems ? (
            <p className="muted">Loading service points...</p>
          ) : (
            <div className="service-points-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card service-points-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="service-points-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Service point list</h2>
                <p className="muted">
                  Browse the existing service-point surface and keep direct drill-down into
                  bounded detail routes.
                </p>
              </div>
            </div>

            <div className="meter-list">
              {!isLoadingItems && items.length === 0 ? (
                <p className="muted">No service points available for the current query.</p>
              ) : null}

              {items.map((item) => (
                <div
                  key={item.id}
                  className={`meter-list-item service-point-list-item${
                    selectedServicePoint?.id === item.id ? " selected" : ""
                  }`}
                >
                  <div className="command-list-item-header">
                    <strong>{item.service_point_code}</strong>
                    <span
                      className={`status-pill ${buildStatusTone(
                        item.is_active ? "active" : "inactive",
                      )}`}
                    >
                      {item.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {formatStatusLabel(item.premises_type ?? "premise")}
                    </span>
                    <span className="artifact-pill">
                      {item.primary_subscriber_display_name ?? "No linked subscriber"}
                    </span>
                    <span className="artifact-pill">
                      {item.primary_meter_serial_number
                        ? `Meter ${item.primary_meter_serial_number}`
                        : "No linked meter"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Service point ID {item.id}</span>
                    <span>{item.address_line ?? "No address summary"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {item.latitude !== null && item.longitude !== null
                        ? `${item.latitude}, ${item.longitude}`
                        : "No coordinate summary"}
                    </span>
                    <span>{item.linked_account_count} linked account(s)</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{item.linked_meter_count} linked meter(s)</span>
                    <span>{item.linked_subscriber_count} linked subscriber(s)</span>
                  </div>
                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedServicePointId(item.id)}
                      type="button"
                    >
                      Inspect summary
                    </button>
                    <Link className="secondary-button" href={`/service-points/${item.id}`}>
                      Open service point detail
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Selected service point summary</h2>
                <p className="muted">
                  Bounded inline review of location, subscriber, account, and meter
                  linkage before opening the existing service-point detail route.
                </p>
              </div>
            </div>

            {isLoadingItems ? (
              <p className="muted">Loading selected service point summary...</p>
            ) : selectedServicePoint ? (
              <div className="detail-stack">
                <section className="service-point-detail-hero">
                  <div className="service-point-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Service Point</p>
                      <h3>{selectedServicePoint.service_point_code}</h3>
                      <p className="muted">
                        {selectedServicePoint.is_active ? "Active" : "Inactive"}{" "}
                        {formatStatusLabel(selectedServicePoint.premises_type ?? "premise")} with{" "}
                        {selectedServicePoint.linked_meter_count} linked meter(s),{" "}
                        {selectedServicePoint.linked_subscriber_count} linked subscriber(s), and{" "}
                        {selectedServicePoint.linked_account_count} linked account(s).
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(
                        selectedServicePoint.is_active ? "active" : "inactive",
                      )}`}
                    >
                      {selectedServicePoint.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>

                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {selectedServicePoint.address_line ?? "No address summary"}
                    </span>
                    <span className="artifact-pill">
                      {selectedServicePoint.primary_subscriber_display_name ??
                        "No linked subscriber"}
                    </span>
                    <span className="artifact-pill">
                      {selectedServicePoint.primary_meter_serial_number
                        ? `Meter ${selectedServicePoint.primary_meter_serial_number}`
                        : "No linked meter"}
                    </span>
                  </div>
                </section>

                <div className="detail-grid">
                  <div className="stat-card">
                    <span className="stat-label">Service point ID</span>
                    <strong>{selectedServicePoint.id}</strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Premises type</span>
                    <strong>
                      {formatStatusLabel(selectedServicePoint.premises_type ?? "premise")}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Coordinates</span>
                    <strong>
                      {selectedServicePoint.latitude !== null &&
                      selectedServicePoint.longitude !== null
                        ? `${selectedServicePoint.latitude}, ${selectedServicePoint.longitude}`
                        : "Not available"}
                    </strong>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Linked accounts</span>
                    <strong>{selectedServicePoint.linked_account_count}</strong>
                  </div>
                </div>

                <div className="artifact-row">
                  <Link
                    className="secondary-button"
                    href={`/service-points/${selectedServicePoint.id}`}
                  >
                    Open service point detail
                  </Link>
                </div>
              </div>
            ) : (
              <p className="muted">No service point selected for bounded summary review.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
