"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

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

function formatCoordinatePair(latitude: number | null, longitude: number | null): string {
  if (latitude === null || longitude === null) {
    return "Not available";
  }
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
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

  const primaryLinkedMeter = detail?.linked_meters[0] ?? null;
  const primaryLinkedServicePoint = detail?.linked_service_points[0] ?? null;
  const linkedRegisteredMeterCount = useMemo(
    () =>
      detail?.linked_meters.filter((meter) => {
        const normalized = meter.current_status.toLowerCase();
        return normalized.includes("registered") || normalized.includes("active");
      }).length ?? 0,
    [detail?.linked_meters],
  );
  const linkedInactiveServicePointCount = useMemo(
    () =>
      detail?.linked_service_points.filter((servicePoint) => !servicePoint.is_active).length ?? 0,
    [detail?.linked_service_points],
  );
  const distinctPremisesTypes = useMemo(
    () =>
      Array.from(
        new Set(
          (detail?.linked_service_points ?? [])
            .map((servicePoint) => servicePoint.premises_type)
            .filter((premisesType): premisesType is string => Boolean(premisesType)),
        ),
      ),
    [detail?.linked_service_points],
  );
  const networkAssetCards = detail
    ? [
        {
          label: "Network asset",
          value: `${detail.code} · ${detail.name}`,
          note: `${formatStatusLabel(detail.status)} transformer • ${detail.id}`,
        },
        {
          label: "Feeder context",
          value: `${detail.feeder_code} · ${detail.feeder_name}`,
          note: `Parent substation ${detail.substation.code} · ${detail.substation.name}`,
        },
        {
          label: "GIS posture",
          value:
            detail.latitude !== null && detail.longitude !== null
              ? "Transformer coordinates visible"
              : detail.substation.latitude !== null && detail.substation.longitude !== null
                ? "Substation coordinates visible"
                : "No mapped network coordinates",
          note: `Transformer ${formatCoordinatePair(detail.latitude, detail.longitude)} • Substation ${formatCoordinatePair(
            detail.substation.latitude,
            detail.substation.longitude,
          )}`,
        },
        {
          label: "Linked operational estate",
          value: `${detail.linked_meter_count} meter(s) / ${detail.linked_service_point_count} service point(s)`,
          note: `${linkedRegisteredMeterCount} meter(s) currently active or registered • ${linkedInactiveServicePointCount} inactive service point(s)`,
        },
        {
          label: "Primary follow-through",
          value:
            primaryLinkedMeter?.serial_number ??
            primaryLinkedServicePoint?.service_point_code ??
            "No linked operational asset",
          note: primaryLinkedMeter
            ? primaryLinkedServicePoint
              ? `${primaryLinkedServicePoint.service_point_code} • meter and service-point routes available`
              : "Meter route available"
            : primaryLinkedServicePoint
              ? "Service-point route available"
              : "No linked meter or service point route available",
        },
        {
          label: "Premises mix",
          value:
            distinctPremisesTypes.length > 0
              ? distinctPremisesTypes.map((premisesType) => formatStatusLabel(premisesType)).join(", ")
              : "No premises type visible",
          note:
            distinctPremisesTypes.length > 0
              ? "Derived from linked service-point records already in scope"
              : "No linked service-point premises context recorded",
        },
      ]
    : [];
  const networkNarrative = detail
    ? `${formatStatusLabel(detail.status)} transformer ${detail.code} is routed through feeder ${detail.feeder_code} under ${detail.substation.code}, with ${formatCountLabel(
        detail.linked_meter_count,
        "linked meter",
        "linked meters",
      )} and ${formatCountLabel(detail.linked_service_point_count, "linked service point", "linked service points")} available for bounded follow-through.`
    : null;

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
                <span className="artifact-pill">{detail.feeder_code}</span>
                <span className="artifact-pill">
                  {detail.substation.code} · {detail.substation.name}
                </span>
                <span className="artifact-pill">
                  {detail.description ?? "No infrastructure description"}
                </span>
              </div>
              <div className="artifact-row">
                <Link className="secondary-button" href="/transformers-substations">
                  Return to infrastructure list
                </Link>
                <Link
                  className="secondary-button"
                  href={
                    primaryLinkedMeter
                      ? `/gis-lite?meterId=${primaryLinkedMeter.id}`
                      : "/gis-lite"
                  }
                >
                  Open GIS Lite context
                </Link>
                {primaryLinkedMeter ? (
                  <Link className="secondary-button" href={`/meters/${primaryLinkedMeter.id}?tab=gis`}>
                    Open primary meter GIS detail
                  </Link>
                ) : null}
                {primaryLinkedServicePoint ? (
                  <Link
                    className="secondary-button"
                    href={`/service-points/${primaryLinkedServicePoint.id}`}
                  >
                    Open primary service point detail
                  </Link>
                ) : null}
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
                <h3>Network asset workspace</h3>
                <p className="muted">
                  Dense operational summary for the current transformer using only the
                  existing network, GIS, and linked-asset context.
                </p>
              </div>
            </div>
            {networkNarrative ? <p className="muted">{networkNarrative}</p> : null}
            <div className="meter-summary-grid">
              {networkAssetCards.map((card) => (
                <div key={card.label} className="stat-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="muted">{card.note}</p>
                </div>
              ))}
            </div>
            {detail.description ? (
              <p className="muted">{detail.description}</p>
            ) : (
              <p className="muted">No infrastructure description is available.</p>
            )}
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>GIS and location context</h3>
                <p className="muted">
                  Compact coordinate and regional posture for the transformer and its
                  parent substation without expanding the GIS subsystem.
                </p>
              </div>
            </div>
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Transformer coordinates</span>
                <strong>{formatCoordinatePair(detail.latitude, detail.longitude)}</strong>
                <p className="muted">
                  {detail.latitude !== null && detail.longitude !== null
                    ? "Transformer-level mapping is currently visible."
                    : "No transformer-level mapped coordinates are recorded."}
                </p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Substation coordinates</span>
                <strong>
                  {formatCoordinatePair(detail.substation.latitude, detail.substation.longitude)}
                </strong>
                <p className="muted">
                  {detail.substation.latitude !== null && detail.substation.longitude !== null
                    ? "Parent substation mapping is currently visible."
                    : "No mapped parent-substation coordinates are recorded."}
                </p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Sector</span>
                <strong>
                  {detail.substation.sector_code} · {detail.substation.sector_name}
                </strong>
                <p className="muted">Parent substation sector context remains preserved.</p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Region</span>
                <strong>
                  {detail.substation.region_code} · {detail.substation.region_name}
                </strong>
                <p className="muted">Regional network placement remains preserved.</p>
              </div>
            </div>
            <div className="artifact-row">
              <span className="artifact-pill">
                {detail.latitude !== null && detail.longitude !== null
                  ? "Transformer mapping available"
                  : detail.substation.latitude !== null && detail.substation.longitude !== null
                    ? "Substation mapping available"
                    : "No mapped network coordinates"}
              </span>
              <span className="artifact-pill">{detail.substation.code}</span>
              <span className="artifact-pill">{detail.feeder_code}</span>
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Operational linkage cues</h3>
                <p className="muted">
                  Bounded scanability for the network relationship cues already visible from
                  linked meters and service points.
                </p>
              </div>
            </div>
            <div className="meter-summary-grid">
              <div className="stat-card">
                <span className="stat-label">Primary linked meter</span>
                <strong>{primaryLinkedMeter?.serial_number ?? "Not available"}</strong>
                <p className="muted">
                  {primaryLinkedMeter
                    ? `${formatStatusLabel(primaryLinkedMeter.current_status)} • ${primaryLinkedMeter.utility_meter_number ?? "No utility number"}`
                    : "No linked meter is currently available for direct follow-through."}
                </p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Primary linked service point</span>
                <strong>{primaryLinkedServicePoint?.service_point_code ?? "Not available"}</strong>
                <p className="muted">
                  {primaryLinkedServicePoint
                    ? `${formatStatusLabel(primaryLinkedServicePoint.premises_type ?? "premise")} • ${primaryLinkedServicePoint.address_line ?? "No address summary"}`
                    : "No linked service point is currently available for direct follow-through."}
                </p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Registered / active meters</span>
                <strong>{linkedRegisteredMeterCount}</strong>
                <p className="muted">
                  Derived from current linked-meter status values only.
                </p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Inactive service points</span>
                <strong>{linkedInactiveServicePointCount}</strong>
                <p className="muted">
                  Derived from current linked service-point activity only.
                </p>
              </div>
              <div className="stat-card">
                <span className="stat-label">Premises types in scope</span>
                <strong>
                  {distinctPremisesTypes.length > 0
                    ? distinctPremisesTypes.map((premisesType) => formatStatusLabel(premisesType)).join(", ")
                    : "Not available"}
                </strong>
                <p className="muted">
                  Derived from linked service-point premises types only.
                </p>
              </div>
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
