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
    normalized.includes("energized") ||
    normalized.includes("available")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("outage") ||
    normalized.includes("fault") ||
    normalized.includes("offline")
  ) {
    return "danger";
  }
  if (normalized.includes("warning") || normalized.includes("maintenance")) {
    return "warning";
  }
  return "neutral";
}

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function buildLocationPosture(item: TransformerSubstationListItem): string {
  return item.location_hint ? "Location hint available" : "Location hint unavailable";
}

export function TransformersSubstationsModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [items, setItems] = useState<TransformerSubstationListItem[]>([]);
  const [selectedInfrastructureId, setSelectedInfrastructureId] = useState<string | null>(null);
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

  const overviewCards = useMemo(() => {
    const linkedMeters = items.reduce((total, item) => total + item.linked_meter_count, 0);
    const linkedServicePoints = items.reduce(
      (total, item) => total + item.linked_service_point_count,
      0,
    );
    const mappedItems = items.filter((item) => item.location_hint !== null).length;
    const uniqueSubstations = new Set(items.map((item) => item.substation_id)).size;

    return [
      { label: "Infrastructure items in view", value: String(items.length) },
      { label: "Parent substations represented", value: String(uniqueSubstations) },
      { label: "Linked meters represented", value: String(linkedMeters) },
      { label: "Linked service points represented", value: String(linkedServicePoints) },
      { label: "Assets with location hints", value: String(mappedItems) },
    ];
  }, [items]);

  useEffect(() => {
    setSelectedInfrastructureId((currentSelectedInfrastructureId) => {
      if (
        currentSelectedInfrastructureId &&
        items.some((item) => item.id === currentSelectedInfrastructureId)
      ) {
        return currentSelectedInfrastructureId;
      }
      return items[0]?.id ?? null;
    });
  }, [items]);

  const selectedInfrastructure = useMemo(
    () => items.find((item) => item.id === selectedInfrastructureId) ?? items[0] ?? null,
    [items, selectedInfrastructureId],
  );
  const selectedInfrastructureCards = useMemo(() => {
    if (!selectedInfrastructure) {
      return [];
    }

    return [
      {
        label: "Network asset",
        value: `${selectedInfrastructure.code} · ${selectedInfrastructure.name}`,
        note: `${formatStatusLabel(selectedInfrastructure.status)} transformer • ${selectedInfrastructure.id}`,
      },
      {
        label: "Feeder / substation",
        value: `${selectedInfrastructure.feeder_code} • ${selectedInfrastructure.substation_code}`,
        note: `${selectedInfrastructure.substation_code} · ${selectedInfrastructure.substation_name}`,
      },
      {
        label: "Location posture",
        value: buildLocationPosture(selectedInfrastructure),
        note: selectedInfrastructure.location_hint ?? "No list-level location hint is available",
      },
      {
        label: "Linked operational estate",
        value: `${selectedInfrastructure.linked_meter_count} meter(s) / ${selectedInfrastructure.linked_service_point_count} service point(s)`,
        note: `${selectedInfrastructure.primary_meter_serial_number ?? "No primary meter"} • ${selectedInfrastructure.primary_service_point_code ?? "No primary service point"}`,
      },
      {
        label: "Primary follow-through",
        value:
          selectedInfrastructure.primary_meter_serial_number ??
          selectedInfrastructure.primary_service_point_code ??
          "No primary linked asset",
        note: selectedInfrastructure.primary_meter_serial_number
          ? selectedInfrastructure.primary_service_point_code
            ? "Primary meter and service-point cues are visible in list context"
            : "Primary meter cue is visible in list context"
          : selectedInfrastructure.primary_service_point_code
            ? "Primary service-point cue is visible in list context"
            : "No primary linked asset is visible in list context",
      },
    ];
  }, [selectedInfrastructure]);
  const selectedInfrastructureNarrative = useMemo(() => {
    if (!selectedInfrastructure) {
      return null;
    }

    return `${formatStatusLabel(selectedInfrastructure.status)} transformer ${selectedInfrastructure.code} sits on feeder ${selectedInfrastructure.feeder_code} under ${selectedInfrastructure.substation_code}, with ${formatCountLabel(
      selectedInfrastructure.linked_meter_count,
      "linked meter",
      "linked meters",
    )} and ${formatCountLabel(
      selectedInfrastructure.linked_service_point_count,
      "linked service point",
      "linked service points",
    )} visible before opening the detail route.`;
  }, [selectedInfrastructure]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel infrastructure-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Infrastructure operations center</h2>
              <p className="muted">
                Read-only infrastructure visibility across transformers, parent
                substations, feeders, and linked operational context.
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
          ) : (
            <div className="infrastructure-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card infrastructure-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="infrastructure-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Transformer list</h2>
                <p className="muted">
                  Browse the existing infrastructure surface and keep direct drill-down
                  into the bounded transformer detail route.
                </p>
              </div>
            </div>

            <div className="meter-list">
              {!isLoadingItems && items.length === 0 ? (
                <p className="muted">
                  No transformer or substation visibility is available for the current query.
                </p>
              ) : null}

              {items.map((item) => (
                <div
                  key={item.id}
                  className={`meter-list-item infrastructure-list-item${
                    selectedInfrastructure?.id === item.id ? " selected" : ""
                  }`}
                >
                  <div className="command-list-item-header">
                    <strong>
                      {item.code} · {item.name}
                    </strong>
                    <span className={`status-pill ${buildStatusTone(item.status)}`}>
                      {formatStatusLabel(item.status)}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span className="artifact-pill">Feeder {item.feeder_code}</span>
                    <span className="artifact-pill">
                      {item.substation_code} · {item.substation_name}
                    </span>
                    <span className={`status-pill ${buildStatusTone(buildLocationPosture(item))}`}>
                      {buildLocationPosture(item)}
                    </span>
                    <span className="artifact-pill">
                      {item.location_hint ?? "No location hint"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Transformer ID {item.id}</span>
                    <span>Substation {item.substation_id}</span>
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
                  <div className="command-list-item-meta">
                    <span>
                      {item.primary_meter_serial_number
                        ? `Primary meter cue ${item.primary_meter_serial_number}`
                        : "No primary meter cue"}
                    </span>
                    <span>
                      {item.primary_service_point_code
                        ? `Primary service-point cue ${item.primary_service_point_code}`
                        : "No primary service-point cue"}
                    </span>
                  </div>
                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedInfrastructureId(item.id)}
                      type="button"
                    >
                      Inspect summary
                    </button>
                    <Link className="secondary-button" href={`/transformers-substations/${item.id}`}>
                      Open infrastructure detail
                    </Link>
                    <Link className="secondary-button" href="/gis-lite">
                      Open GIS Lite surface
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Selected infrastructure summary</h2>
                <p className="muted">
                  Bounded inline review of transformer, parent substation, feeder, and
                  linked operational context before opening the existing detail route.
                </p>
              </div>
              {selectedInfrastructure ? (
                <span className={`status-pill ${buildStatusTone(selectedInfrastructure.status)}`}>
                  {formatStatusLabel(selectedInfrastructure.status)}
                </span>
              ) : null}
            </div>

            {isLoadingItems ? (
              <p className="muted">Loading selected infrastructure summary...</p>
            ) : selectedInfrastructure ? (
              <div className="detail-stack">
                <section className="infrastructure-detail-hero">
                  <div className="infrastructure-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Infrastructure</p>
                      <h3>
                        {selectedInfrastructure.code} · {selectedInfrastructure.name}
                      </h3>
                      <p className="muted">
                        {formatStatusLabel(selectedInfrastructure.status)} transformer on feeder{" "}
                        {selectedInfrastructure.feeder_code} under substation{" "}
                        {selectedInfrastructure.substation_code} with{" "}
                        {selectedInfrastructure.linked_meter_count} linked meter(s) and{" "}
                        {selectedInfrastructure.linked_service_point_count} linked service
                        point(s).
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(
                        selectedInfrastructure.status,
                      )}`}
                    >
                      {formatStatusLabel(selectedInfrastructure.status)}
                    </span>
                  </div>

                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {selectedInfrastructure.substation_code} ·{" "}
                      {selectedInfrastructure.substation_name}
                    </span>
                    <span className="artifact-pill">
                      {selectedInfrastructure.location_hint ?? "No location hint"}
                    </span>
                    <span className="artifact-pill">
                      {selectedInfrastructure.primary_meter_serial_number
                        ? `Meter ${selectedInfrastructure.primary_meter_serial_number}`
                        : "No linked meter"}
                    </span>
                  </div>
                </section>

                {selectedInfrastructureNarrative ? (
                  <p className="muted">{selectedInfrastructureNarrative}</p>
                ) : null}

                <div className="artifact-row">
                  <span className="artifact-pill">
                    {buildLocationPosture(selectedInfrastructure)}
                  </span>
                  <span className="artifact-pill">
                    {selectedInfrastructure.substation_code} · {selectedInfrastructure.substation_name}
                  </span>
                  <span className="artifact-pill">
                    {selectedInfrastructure.primary_meter_serial_number
                      ? `Primary meter ${selectedInfrastructure.primary_meter_serial_number}`
                      : "No primary meter"}
                  </span>
                  <span className="artifact-pill">
                    {selectedInfrastructure.primary_service_point_code
                      ? `Primary service point ${selectedInfrastructure.primary_service_point_code}`
                      : "No primary service point"}
                  </span>
                </div>

                <div className="detail-grid">
                  {selectedInfrastructureCards.map((card) => (
                    <div key={card.label} className="stat-card">
                      <span className="stat-label">{card.label}</span>
                      <strong>{card.value}</strong>
                      <p className="muted">{card.note}</p>
                    </div>
                  ))}
                </div>

                <div className="artifact-row">
                  <Link
                    className="secondary-button"
                    href={`/transformers-substations/${selectedInfrastructure.id}`}
                  >
                    Open infrastructure detail
                  </Link>
                  <Link className="secondary-button" href="/gis-lite">
                    Open GIS Lite surface
                  </Link>
                </div>
              </div>
            ) : (
              <p className="muted">No infrastructure item selected for bounded summary review.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
