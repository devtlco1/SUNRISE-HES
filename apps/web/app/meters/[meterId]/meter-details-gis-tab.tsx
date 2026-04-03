"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type MeterDetail = {
  id: string;
  serial_number: string;
  transformer_id: string | null;
};

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

function formatStatusLabel(value: string | null): string {
  if (!value) {
    return "Not available";
  }

  return value
    .split(/[_\s/.-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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

function formatCoordinates(entity: GisLiteEntity | null): string {
  if (!entity?.has_coordinates || entity.latitude === null || entity.longitude === null) {
    return "Not available";
  }
  return `${entity.latitude}, ${entity.longitude}`;
}

export function MeterDetailsGisTab({
  meterId,
  meter,
  linkedServicePointId,
  linkedServicePointCode,
  authorizedFetch,
}: {
  meterId: string;
  meter: MeterDetail | null;
  linkedServicePointId: string | null;
  linkedServicePointCode: string | null;
  authorizedFetch: AuthorizedFetch;
}) {
  const [gisEntity, setGisEntity] = useState<GisLiteEntity | null>(null);
  const [gisTotal, setGisTotal] = useState(0);
  const [gisError, setGisError] = useState<string | null>(null);
  const [isLoadingGis, setIsLoadingGis] = useState(false);

  const loadGisEntity = useCallback(async () => {
    setIsLoadingGis(true);
    setGisError(null);

    try {
      const response = await authorizedFetch<GisLiteEntityListResponse>(
        `/api/v1/gis-lite/entities?limit=1&meter_id=${meterId}`,
      );
      setGisEntity(response.items[0] ?? null);
      setGisTotal(response.total);
    } catch (error) {
      setGisEntity(null);
      setGisTotal(0);
      setGisError(error instanceof Error ? error.message : "Unable to load meter GIS context.");
    } finally {
      setIsLoadingGis(false);
    }
  }, [authorizedFetch, meterId]);

  useEffect(() => {
    void loadGisEntity();
  }, [loadGisEntity]);

  const effectiveServicePointId = gisEntity?.service_point_id ?? linkedServicePointId;
  const effectiveServicePointCode = gisEntity?.service_point_code ?? linkedServicePointCode;

  const overviewCards = useMemo(
    () => [
      {
        label: "Mapping status",
        value: gisEntity ? formatLocationPresence(gisEntity.location_presence) : "Not available",
        note: gisEntity?.has_coordinates
          ? "Spatial coordinates are available for this meter-linked location"
          : "Location detail is bounded to existing service-point linkage only",
      },
      {
        label: "Coordinates",
        value: formatCoordinates(gisEntity),
        note: gisEntity?.address_line ?? "No mapped address recorded",
      },
      {
        label: "Service point",
        value: effectiveServicePointCode ?? "Not available",
        note: effectiveServicePointId ?? "No linked service point",
      },
      {
        label: "Transformer",
        value: meter?.transformer_id ?? "Not available",
        note: meter?.transformer_id
          ? "Existing transformer context preserved on the meter record"
          : "No transformer linkage recorded",
      },
      {
        label: "Subscriber / account",
        value: gisEntity?.subscriber_display_name ?? gisEntity?.account_number ?? "Not available",
        note:
          gisEntity?.account_number ??
          gisEntity?.subscriber_type ??
          "No linked subscriber or account recorded",
      },
      {
        label: "GIS freshness",
        value: formatDateTime(gisEntity?.meter_last_seen_at ?? null),
        note: gisEntity ? formatStatusLabel(gisEntity.meter_status) : "No GIS-linked entity loaded",
      },
    ],
    [effectiveServicePointCode, effectiveServicePointId, gisEntity, meter?.transformer_id],
  );

  return (
    <div className="detail-stack">
      {gisError ? <p className="error-banner">{gisError}</p> : null}

      <section className="subpanel audit-center-overview-panel">
        <div className="section-heading">
          <div>
            <h2>GIS context</h2>
            <p className="muted">
              Meter-scoped spatial, service-point, and network context using the existing
              GIS Lite read model only.
            </p>
          </div>
          <div className="artifact-row">
            <span className="artifact-pill">
              {isLoadingGis
                ? "Loading GIS context"
                : `${gisTotal} GIS-linked entit${gisTotal === 1 ? "y" : "ies"} in scope`}
            </span>
            <Link className="secondary-button" href="/gis-lite">
              Open GIS Lite surface
            </Link>
          </div>
        </div>

        {isLoadingGis ? <p className="muted">Loading meter GIS context...</p> : null}

        {!isLoadingGis && gisEntity ? (
          <div className="detail-stack">
            <div className="meter-summary-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>

            <div className="artifact-row">
              <span
                className={`status-pill ${buildStatusTone(
                  formatLocationPresence(gisEntity.location_presence),
                )}`}
              >
                {formatLocationPresence(gisEntity.location_presence)}
              </span>
              <span className={`status-pill ${buildStatusTone(gisEntity.meter_status)}`}>
                {formatStatusLabel(gisEntity.meter_status)}
              </span>
              <span className="artifact-pill">
                {gisEntity.address_line ?? "No mapped address"}
              </span>
            </div>
          </div>
        ) : null}

        {!isLoadingGis && !gisEntity ? (
          <p className="muted">GIS context not available for this meter yet.</p>
        ) : null}
      </section>

      <section className="subpanel meter-summary-panel">
        <div className="section-heading">
          <div>
            <h2>Network and location navigation</h2>
            <p className="muted">
              Continue into the existing GIS Lite, service-point, transformer, and
              subscriber detail surfaces when deeper spatial review is needed.
            </p>
          </div>
        </div>

        {isLoadingGis ? (
          <p className="muted">Loading GIS navigation context...</p>
        ) : (
          <div className="detail-stack">
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Meter</span>
                <strong>{meter?.serial_number ?? "Not available"}</strong>
                <p className="muted">{meter?.id ?? "No meter identity recorded"}</p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Service point link</span>
                <strong>{effectiveServicePointCode ?? "Not available"}</strong>
                <p className="muted">{effectiveServicePointId ?? "No service point linked"}</p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Transformer link</span>
                <strong>{meter?.transformer_id ?? "Not available"}</strong>
                <p className="muted">Existing transformer/substation surface preserved</p>
              </div>
            </div>

            <div className="artifact-row">
              {effectiveServicePointId ? (
                <Link
                  className="secondary-button"
                  href={`/service-points/${effectiveServicePointId}`}
                >
                  Open service point detail
                </Link>
              ) : null}
              {meter?.transformer_id ? (
                <Link
                  className="secondary-button"
                  href={`/transformers-substations/${meter.transformer_id}`}
                >
                  Open transformer detail
                </Link>
              ) : null}
              {gisEntity?.subscriber_id ? (
                <Link className="secondary-button" href={`/subscribers/${gisEntity.subscriber_id}`}>
                  Open subscriber detail
                </Link>
              ) : null}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
