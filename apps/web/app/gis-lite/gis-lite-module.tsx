"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type GisLiteEntity = {
  meter_id: string;
  meter_serial_number: string;
  meter_status: string;
  meter_last_seen_at: string | null;
  service_point_id: string | null;
  service_point_code: string | null;
  address_line: string | null;
  latitude: number | null;
  longitude: number | null;
  has_coordinates: boolean;
  subscriber_id: string | null;
  subscriber_display_name: string | null;
  subscriber_type: string | null;
  account_id: string | null;
  account_number: string | null;
  location_presence: "coordinates_available" | "service_point_only" | "unlinked";
};

type GisLiteEntityListResponse = {
  total: number;
  items: GisLiteEntity[];
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
    normalized.includes("commissioned") ||
    normalized.includes("registered") ||
    normalized.includes("active") ||
    normalized.includes("coordinates")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("disconnected") ||
    normalized.includes("error") ||
    normalized.includes("unlinked")
  ) {
    return "danger";
  }
  if (normalized.includes("service point only") || normalized.includes("pending")) {
    return "warning";
  }
  return "neutral";
}

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

function formatLocationPresence(value: GisLiteEntity["location_presence"]): string {
  if (value === "coordinates_available") {
    return "Coordinates available";
  }
  if (value === "service_point_only") {
    return "Service point only";
  }
  return "No linked location";
}

function normalizeCoordinate(
  value: number,
  min: number,
  max: number,
  invert = false,
): string {
  if (min === max) {
    return "50%";
  }
  const ratio = (value - min) / (max - min);
  const normalized = invert ? 1 - ratio : ratio;
  return `${Math.max(8, Math.min(92, normalized * 100))}%`;
}

export function GisLiteModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [items, setItems] = useState<GisLiteEntity[]>([]);
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
  const [totalItems, setTotalItems] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingEntities, setIsLoadingEntities] = useState(false);

  const loadEntities = useCallback(async () => {
    setIsLoadingEntities(true);
    setPageError(null);

    try {
      const response = await authorizedFetch<GisLiteEntityListResponse>(
        "/api/v1/gis-lite/entities?limit=24",
      );
      setItems(response.items);
      setTotalItems(response.total);
    } catch (error) {
      setItems([]);
      setTotalItems(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load GIS Lite view.",
      );
    } finally {
      setIsLoadingEntities(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    void loadEntities();
  }, [loadEntities]);

  const itemsWithCoordinates = useMemo(
    () =>
      items.filter(
        (item): item is GisLiteEntity & { latitude: number; longitude: number } =>
          item.latitude !== null && item.longitude !== null,
      ),
    [items],
  );

  const mapBounds = useMemo(() => {
    if (itemsWithCoordinates.length === 0) {
      return null;
    }
    return {
      minLatitude: Math.min(...itemsWithCoordinates.map((item) => item.latitude)),
      maxLatitude: Math.max(...itemsWithCoordinates.map((item) => item.latitude)),
      minLongitude: Math.min(...itemsWithCoordinates.map((item) => item.longitude)),
      maxLongitude: Math.max(...itemsWithCoordinates.map((item) => item.longitude)),
    };
  }, [itemsWithCoordinates]);

  const overview = useMemo(
    () => ({
      withCoordinates: items.filter((item) => item.has_coordinates).length,
      withSubscribers: items.filter((item) => item.subscriber_id !== null).length,
      linkedAccounts: items.filter((item) => item.account_id !== null).length,
      locationGaps: items.filter((item) => item.location_presence !== "coordinates_available").length,
    }),
    [items],
  );

  useEffect(() => {
    setSelectedMeterId((currentSelectedMeterId) => {
      if (currentSelectedMeterId && items.some((item) => item.meter_id === currentSelectedMeterId)) {
        return currentSelectedMeterId;
      }
      return items[0]?.meter_id ?? null;
    });
  }, [items]);

  const selectedEntity = useMemo(
    () => items.find((item) => item.meter_id === selectedMeterId) ?? items[0] ?? null,
    [items, selectedMeterId],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel gis-overview-panel">
          <div className="section-heading">
            <div>
              <h2>GIS operations center</h2>
              <p className="muted">
                Bounded GIS-lite visibility over existing meter and subscriber-linked
                service-point context.
              </p>
            </div>
            <span className="artifact-pill">{totalItems} entities in scope</span>
          </div>

          {isLoadingEntities ? (
            <p className="muted">Loading GIS Lite overview...</p>
          ) : (
            <div className="gis-overview-grid">
              <div className="stat-card gis-overview-card">
                <span className="stat-label">Items loaded</span>
                <strong>{items.length}</strong>
              </div>
              <div className="stat-card gis-overview-card">
                <span className="stat-label">With coordinates</span>
                <strong>{overview.withCoordinates}</strong>
              </div>
              <div className="stat-card gis-overview-card">
                <span className="stat-label">With linked subscriber</span>
                <strong>{overview.withSubscribers}</strong>
              </div>
              <div className="stat-card gis-overview-card">
                <span className="stat-label">With linked account</span>
                <strong>{overview.linkedAccounts}</strong>
              </div>
              <div className="stat-card gis-overview-card">
                <span className="stat-label">Location gaps</span>
                <strong>{overview.locationGaps}</strong>
              </div>
            </div>
          )}
        </section>

        <div className="gis-module-layout">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Marker view</h2>
              <p className="muted">
                Lightweight marker visibility when coordinates are available, with a
                graceful list-first fallback otherwise.
              </p>
            </div>
          </div>

          {isLoadingEntities ? (
            <p className="muted">Loading GIS Lite markers...</p>
          ) : null}

          {!isLoadingEntities && itemsWithCoordinates.length === 0 ? (
            <p className="muted">
              No coordinates are currently available. Showing list-first GIS Lite
              visibility only.
            </p>
          ) : null}

          {!isLoadingEntities && mapBounds ? (
            <div className="detail-stack">
              <div className="gis-map-legend">
                <span className="artifact-pill">{itemsWithCoordinates.length} mapped meter(s)</span>
                <span className="artifact-pill">{overview.locationGaps} location gap(s)</span>
                <span className="artifact-pill">Existing meter routes preserved</span>
              </div>
              <div className="gis-map-shell">
                {itemsWithCoordinates.map((item) => (
                  <button
                    key={item.meter_id}
                    aria-label={`Inspect ${item.meter_serial_number}`}
                    className={`secondary-button gis-map-marker${
                      selectedEntity?.meter_id === item.meter_id ? " selected" : ""
                    }`}
                    onClick={() => setSelectedMeterId(item.meter_id)}
                    style={{
                      left: normalizeCoordinate(
                        item.longitude,
                        mapBounds.minLongitude,
                        mapBounds.maxLongitude,
                      ),
                      top: normalizeCoordinate(
                        item.latitude,
                        mapBounds.minLatitude,
                        mapBounds.maxLatitude,
                        true,
                      ),
                    }}
                    type="button"
                  >
                    {item.meter_serial_number}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Selected spatial entity</h2>
              <p className="muted">
                Bounded inline summary for the currently selected GIS-linked entity before
                drilling into the existing operational detail routes.
              </p>
            </div>
          </div>

          {isLoadingEntities ? (
            <p className="muted">Loading selected GIS entity...</p>
          ) : selectedEntity ? (
            <div className="detail-stack">
              <section className="gis-detail-hero">
                <div className="gis-detail-title-row">
                  <div>
                    <p className="eyebrow">Selected Entity</p>
                    <h3>{selectedEntity.meter_serial_number}</h3>
                    <p className="muted">
                      {formatStatusLabel(selectedEntity.meter_status)} meter in{" "}
                      {formatLocationPresence(selectedEntity.location_presence).toLowerCase()} mode
                      with service-point and subscriber linkage preserved.
                    </p>
                  </div>
                  <span className={`status-pill ${buildStatusTone(selectedEntity.meter_status)}`}>
                    {formatStatusLabel(selectedEntity.meter_status)}
                  </span>
                </div>

                <div className="command-list-item-badges">
                  <span
                    className={`status-pill ${buildStatusTone(
                      formatLocationPresence(selectedEntity.location_presence),
                    )}`}
                  >
                    {formatLocationPresence(selectedEntity.location_presence)}
                  </span>
                  <span className="artifact-pill">
                    {selectedEntity.service_point_code ?? "No service point"}
                  </span>
                  <span className="artifact-pill">
                    {selectedEntity.account_number ?? "No account"}
                  </span>
                </div>
              </section>

              <div className="detail-grid">
                <div className="stat-card">
                  <span className="stat-label">Meter ID</span>
                  <strong>{selectedEntity.meter_id}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Subscriber</span>
                  <strong>{selectedEntity.subscriber_display_name ?? "Not available"}</strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Coordinates</span>
                  <strong>
                    {selectedEntity.has_coordinates
                      ? `${selectedEntity.latitude}, ${selectedEntity.longitude}`
                      : "Not available"}
                  </strong>
                </div>
                <div className="stat-card">
                  <span className="stat-label">Last seen</span>
                  <strong>{formatDateTime(selectedEntity.meter_last_seen_at)}</strong>
                </div>
              </div>

              <div className="artifact-row">
                <Link className="secondary-button" href={`/meters/${selectedEntity.meter_id}`}>
                  Open meter detail
                </Link>
                {selectedEntity.subscriber_id ? (
                  <Link
                    className="secondary-button"
                    href={`/subscribers/${selectedEntity.subscriber_id}`}
                  >
                    Open subscriber detail
                  </Link>
                ) : null}
              </div>
            </div>
          ) : (
            <p className="muted">No GIS entity selected for bounded summary review.</p>
          )}
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>GIS-linked entities</h2>
              <p className="muted">
                Select an entity to continue into the existing meter or subscriber
                detail surfaces.
              </p>
            </div>
          </div>

          {isLoadingEntities ? (
            <p className="muted">Loading GIS-linked entities...</p>
          ) : null}

          <div className="meter-list">
            {!isLoadingEntities && items.length === 0 ? (
              <p className="muted">No GIS-linked entities available.</p>
            ) : null}

            {items.map((item) => (
              <div
                key={item.meter_id}
                className={`meter-list-item gis-entity-item${
                  selectedEntity?.meter_id === item.meter_id ? " selected" : ""
                }`}
              >
                <div className="command-list-item-header">
                  <strong>{item.meter_serial_number}</strong>
                  <span className={`status-pill ${buildStatusTone(item.meter_status)}`}>
                    {formatStatusLabel(item.meter_status)}
                  </span>
                </div>
                <div className="command-list-item-badges">
                  <span
                    className={`status-pill ${buildStatusTone(
                      formatLocationPresence(item.location_presence),
                    )}`}
                  >
                    {formatLocationPresence(item.location_presence)}
                  </span>
                  <span className="artifact-pill">
                    {item.service_point_code ?? "No service point"}
                  </span>
                  <span className="artifact-pill">
                    {item.account_number ?? "No account"}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>Meter ID {item.meter_id}</span>
                  <span>Last seen {formatDateTime(item.meter_last_seen_at)}</span>
                </div>
                <div className="command-list-item-meta">
                  <span>
                    {item.service_point_code ?? "No service point"}{" "}
                    {item.address_line ? `- ${item.address_line}` : ""}
                  </span>
                  <span>
                    {item.subscriber_display_name ?? "No linked subscriber"}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>
                    {item.has_coordinates
                      ? `${item.latitude}, ${item.longitude}`
                      : "Coordinates not available"}
                  </span>
                  <span>{item.subscriber_type ? formatStatusLabel(item.subscriber_type) : "No subscriber type"}</span>
                </div>
                <div className="artifact-row">
                  <button
                    className="secondary-button"
                    onClick={() => setSelectedMeterId(item.meter_id)}
                    type="button"
                  >
                    Inspect summary
                  </button>
                  <Link className="secondary-button" href={`/meters/${item.meter_id}`}>
                    Open meter detail
                  </Link>
                  {item.subscriber_id ? (
                    <Link
                      className="secondary-button"
                      href={`/subscribers/${item.subscriber_id}`}
                    >
                      Open subscriber detail
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>
        </div>
      </div>
    </section>
  );
}
