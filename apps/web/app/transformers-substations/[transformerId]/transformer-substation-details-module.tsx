"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type TransformerSubstationParent = {
  id: string;
  code: string;
  name: string;
  status: string;
  sector_code: string;
  sector_name: string;
  region_code: string;
  region_name: string;
  latitude: number | null;
  longitude: number | null;
};

type LinkedMeter = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  current_status: string;
  service_point_id: string | null;
  service_point_code: string | null;
};

type LinkedServicePoint = {
  id: string;
  service_point_code: string;
  address_line: string | null;
  premises_type: string | null;
  is_active: boolean;
};

type TransformerSubstationDetail = {
  id: string;
  code: string;
  name: string;
  status: string;
  description: string | null;
  feeder_code: string;
  feeder_name: string;
  latitude: number | null;
  longitude: number | null;
  substation: TransformerSubstationParent;
  linked_meter_count: number;
  linked_service_point_count: number;
  linked_meters: LinkedMeter[];
  linked_service_points: LinkedServicePoint[];
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
    normalized.includes("registered") ||
    normalized.includes("energized")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("fault") ||
    normalized.includes("outage") ||
    normalized.includes("offline")
  ) {
    return "danger";
  }
  if (normalized.includes("warning") || normalized.includes("maintenance")) {
    return "warning";
  }
  return "neutral";
}

export function TransformerSubstationDetailsModule({
  transformerId,
  authorizedFetch,
}: {
  transformerId: string;
  authorizedFetch: AuthorizedFetch;
}) {
  const [detail, setDetail] = useState<TransformerSubstationDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const loadDetail = useCallback(async () => {
    setIsLoadingDetail(true);
    setDetailError(null);

    try {
      const response = await authorizedFetch<TransformerSubstationDetail>(
        `/api/v1/transformers-substations/${transformerId}`,
      );
      setDetail(response);
    } catch (error) {
      setDetail(null);
      setDetailError(
        error instanceof Error
          ? error.message
          : "Unable to load transformer and substation detail.",
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, [authorizedFetch, transformerId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  return (
    <section className="panel">
      {detailError ? <p className="error-banner">{detailError}</p> : null}
      {isLoadingDetail ? (
        <p className="muted">Loading transformer and substation detail...</p>
      ) : null}

      {detail ? (
        <>
          <section className="subpanel infrastructure-overview-panel">
            <section className="infrastructure-detail-hero">
              <div className="infrastructure-detail-title-row">
                <div>
                  <p className="eyebrow">Infrastructure Detail</p>
                  <h2>
                    {detail.code} · {detail.name}
                  </h2>
                  <p className="muted">
                    {formatStatusLabel(detail.status)} transformer in feeder {detail.feeder_code} with{" "}
                    {detail.linked_meter_count} linked meter(s) and{" "}
                    {detail.linked_service_point_count} linked service point(s).
                  </p>
                </div>
                <span className={`status-pill ${buildStatusTone(detail.status)}`}>
                  {formatStatusLabel(detail.status)}
                </span>
              </div>

              <div className="command-list-item-badges">
                <span className="artifact-pill">Transformer {detail.id}</span>
                <span className="artifact-pill">
                  {detail.substation.code} · {detail.substation.name}
                </span>
                <span className="artifact-pill">
                  {detail.description ?? "No infrastructure description"}
                </span>
              </div>
            </section>

            <div className="infrastructure-overview-grid">
              <div className="stat-card infrastructure-overview-card">
                <span className="stat-label">Feeder</span>
                <strong>
                  {detail.feeder_code} · {detail.feeder_name}
                </strong>
              </div>
              <div className="stat-card infrastructure-overview-card">
                <span className="stat-label">Substation</span>
                <strong>
                  {detail.substation.code} · {detail.substation.name}
                </strong>
              </div>
              <div className="stat-card infrastructure-overview-card">
                <span className="stat-label">Linked meters</span>
                <strong>{detail.linked_meter_count}</strong>
              </div>
              <div className="stat-card infrastructure-overview-card">
                <span className="stat-label">Linked service points</span>
                <strong>{detail.linked_service_point_count}</strong>
              </div>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Infrastructure summary</h3>
                <p className="muted">
                  Compact transformer identifiers with bounded parent substation and
                  location context.
                </p>
              </div>
            </div>
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Transformer ID</span>
                <strong>{detail.id}</strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Feeder</span>
                <strong>
                  {detail.feeder_code} · {detail.feeder_name}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Substation</span>
                <strong>
                  {detail.substation.code} · {detail.substation.name}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Sector</span>
                <strong>
                  {detail.substation.sector_code} · {detail.substation.sector_name}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Region</span>
                <strong>
                  {detail.substation.region_code} · {detail.substation.region_name}
                </strong>
              </div>
              <div className="stat-card">
                <span className="stat-label">Location</span>
                <strong>
                  {detail.latitude !== null && detail.longitude !== null
                    ? `${detail.latitude.toFixed(5)}, ${detail.longitude.toFixed(5)}`
                    : "Not available"}
                </strong>
              </div>
            </div>
            {detail.description ? (
              <p className="muted">{detail.description}</p>
            ) : (
              <p className="muted">No infrastructure description is available.</p>
            )}
            <div className="artifact-row">
              <Link className="secondary-button" href="/gis-lite">
                Open GIS Lite
              </Link>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Parent substation context</h3>
                <p className="muted">
                  Read-only substation visibility without expanding into hierarchy
                  editing.
                </p>
              </div>
              <span className={`status-pill ${buildStatusTone(detail.substation.status)}`}>
                {formatStatusLabel(detail.substation.status)}
              </span>
            </div>
            <div className="meter-list">
              <div className="meter-list-item">
                <div className="command-list-item-header">
                  <strong>
                    {detail.substation.code} · {detail.substation.name}
                  </strong>
                  <span className={`status-pill ${buildStatusTone(detail.substation.status)}`}>
                    {formatStatusLabel(detail.substation.status)}
                  </span>
                </div>
                <div className="command-list-item-badges">
                  <span className="artifact-pill">
                    Sector {detail.substation.sector_code} · {detail.substation.sector_name}
                  </span>
                  <span className="artifact-pill">
                    Region {detail.substation.region_code} · {detail.substation.region_name}
                  </span>
                </div>
                <div className="command-list-item-meta">
                  <span>Substation ID {detail.substation.id}</span>
                  <span>
                    Region {detail.substation.region_code} · {detail.substation.region_name}
                  </span>
                  <span>
                    {detail.substation.latitude !== null &&
                    detail.substation.longitude !== null
                      ? `${detail.substation.latitude.toFixed(5)}, ${detail.substation.longitude.toFixed(5)}`
                      : "No mapped substation location"}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked service points</h3>
                <p className="muted">
                  Existing service-point pages linked from the selected transformer.
                </p>
              </div>
              <span className="artifact-pill">
                {detail.linked_service_points.length} service point(s)
              </span>
            </div>
            <div className="meter-list">
              {detail.linked_service_points.length === 0 ? (
                <p className="muted">No linked service points for this transformer.</p>
              ) : null}
              {detail.linked_service_points.map((servicePoint) => (
                <Link
                  key={servicePoint.id}
                  className="meter-list-item"
                  href={`/service-points/${servicePoint.id}`}
                >
                  <div className="command-list-item-header">
                    <strong>{servicePoint.service_point_code}</strong>
                    <span
                      className={`status-pill ${buildStatusTone(
                        servicePoint.is_active ? "active" : "inactive",
                      )}`}
                    >
                      {servicePoint.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {formatStatusLabel(servicePoint.premises_type ?? "premise")}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Service point ID {servicePoint.id}</span>
                    <span>{servicePoint.address_line ?? "No address summary"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Open existing service point detail</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Linked meters</h3>
                <p className="muted">
                  Current operational meter context already linked to this transformer.
                </p>
              </div>
              <span className="artifact-pill">{detail.linked_meters.length} meter(s)</span>
            </div>
            <div className="meter-list">
              {detail.linked_meters.length === 0 ? (
                <p className="muted">No linked meters for this transformer.</p>
              ) : null}
              {detail.linked_meters.map((meter) => (
                <Link key={meter.id} className="meter-list-item" href={`/meters/${meter.id}`}>
                  <div className="command-list-item-header">
                    <strong>{meter.serial_number}</strong>
                    <span className={`status-pill ${buildStatusTone(meter.current_status)}`}>
                      {formatStatusLabel(meter.current_status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {meter.utility_meter_number ?? "No utility number"}
                    </span>
                    <span className="artifact-pill">
                      {meter.service_point_code
                        ? `Service point ${meter.service_point_code}`
                        : "No linked service point"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Meter ID {meter.id}</span>
                    <span>Open existing meter detail</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}
