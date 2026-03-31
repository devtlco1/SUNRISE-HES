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
      locationGaps: items.filter((item) => item.location_presence !== "coordinates_available")
        .length,
    }),
    [items],
  );

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Spatial overview</h2>
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
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Items loaded</span>
                <strong>{items.length}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">With coordinates</span>
                <strong>{overview.withCoordinates}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">With linked subscriber</span>
                <strong>{overview.withSubscribers}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Location gaps</span>
                <strong>{overview.locationGaps}</strong>
              </div>
            </div>
          )}
        </section>

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
            <div
              style={{
                position: "relative",
                minHeight: "18rem",
                border: "1px solid rgba(148, 163, 184, 0.35)",
                borderRadius: "0.75rem",
                background:
                  "linear-gradient(180deg, rgba(15, 23, 42, 0.05), rgba(30, 41, 59, 0.12))",
                overflow: "hidden",
              }}
            >
              {itemsWithCoordinates.map((item) => (
                <Link
                  key={item.meter_id}
                  aria-label={`Open ${item.meter_serial_number}`}
                  className="secondary-button"
                  href={`/meters/${item.meter_id}`}
                  style={{
                    position: "absolute",
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
                    transform: "translate(-50%, -50%)",
                    padding: "0.3rem 0.5rem",
                    minWidth: "auto",
                  }}
                >
                  {item.meter_serial_number}
                </Link>
              ))}
            </div>
          ) : null}
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
              <div key={item.meter_id} className="meter-list-item">
                <div className="command-list-item-header">
                  <strong>{item.meter_serial_number}</strong>
                  <span className="status-pill">{item.meter_status}</span>
                </div>
                <div className="command-list-item-meta">
                  <span>Meter ID {item.meter_id}</span>
                  <span>{formatLocationPresence(item.location_presence)}</span>
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
                  <span>Last seen {formatDateTime(item.meter_last_seen_at)}</span>
                </div>
                <div className="artifact-row">
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
    </section>
  );
}
