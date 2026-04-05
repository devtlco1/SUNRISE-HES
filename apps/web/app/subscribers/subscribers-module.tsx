"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../operational-shell";

type SubscriberListItem = {
  id: string;
  full_name: string;
  consumer_type: string;
  external_ref: string | null;
  national_id: string | null;
  primary_account_number: string | null;
  account_status_summary: string | null;
  active_account_count: number;
  linked_meter_count: number;
  primary_service_point_code: string | null;
};

type SubscriberListResponse = {
  total: number;
  items: SubscriberListItem[];
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
    normalized.includes("linked") ||
    normalized.includes("assigned")
  ) {
    return "positive";
  }
  if (
    normalized.includes("inactive") ||
    normalized.includes("suspend") ||
    normalized.includes("closed") ||
    normalized.includes("blocked")
  ) {
    return "danger";
  }
  if (normalized.includes("pending") || normalized.includes("review")) {
    return "warning";
  }
  return "neutral";
}

function formatCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function buildCommercialPosture(subscriber: SubscriberListItem): string {
  if (subscriber.primary_account_number && subscriber.primary_service_point_code) {
    return "Account and service cues visible";
  }
  if (subscriber.primary_account_number) {
    return "Account cue visible";
  }
  if (subscriber.primary_service_point_code) {
    return "Service cue visible";
  }
  return "Limited commercial cues";
}

function buildIdentifierSummary(subscriber: SubscriberListItem): string {
  return (
    subscriber.external_ref ??
    subscriber.national_id ??
    "No key external identifier"
  );
}

export function SubscribersModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [subscribers, setSubscribers] = useState<SubscriberListItem[]>([]);
  const [selectedSubscriberId, setSelectedSubscriberId] = useState<string | null>(null);
  const [totalSubscribers, setTotalSubscribers] = useState(0);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isLoadingSubscribers, setIsLoadingSubscribers] = useState(false);

  const loadSubscribers = useCallback(async () => {
    setIsLoadingSubscribers(true);
    setPageError(null);

    try {
      const params = new URLSearchParams({
        offset: "0",
        limit: "20",
      });
      if (appliedSearch.trim()) {
        params.set("search", appliedSearch.trim());
      }

      const response = await authorizedFetch<SubscriberListResponse>(
        `/api/v1/consumers?${params.toString()}`,
      );
      setSubscribers(response.items);
      setTotalSubscribers(response.total);
    } catch (error) {
      setSubscribers([]);
      setTotalSubscribers(0);
      setPageError(
        error instanceof Error ? error.message : "Unable to load subscribers.",
      );
    } finally {
      setIsLoadingSubscribers(false);
    }
  }, [appliedSearch, authorizedFetch]);

  useEffect(() => {
    void loadSubscribers();
  }, [loadSubscribers]);

  const statusSummary = useMemo(() => {
    if (appliedSearch.trim()) {
      return `${totalSubscribers} matching subscribers`;
    }
    return `${totalSubscribers} recent subscribers`;
  }, [appliedSearch, totalSubscribers]);

  const overviewCards = useMemo(() => {
    const activeAccounts = subscribers.reduce(
      (total, subscriber) => total + subscriber.active_account_count,
      0,
    );
    const linkedMeters = subscribers.reduce(
      (total, subscriber) => total + subscriber.linked_meter_count,
      0,
    );
    const withServicePoint = subscribers.filter(
      (subscriber) => subscriber.primary_service_point_code !== null,
    ).length;
    const withIdentifiers = subscribers.filter(
      (subscriber) => subscriber.external_ref !== null || subscriber.national_id !== null,
    ).length;

    return [
      {
        label: "Subscribers in current view",
        value: String(subscribers.length),
      },
      {
        label: "Active accounts visible",
        value: String(activeAccounts),
      },
      {
        label: "Primary service points visible",
        value: String(withServicePoint),
      },
      {
        label: "Linked meters visible",
        value: String(linkedMeters),
      },
      {
        label: "Identifiers visible",
        value: String(withIdentifiers),
      },
    ];
  }, [subscribers]);

  useEffect(() => {
    setSelectedSubscriberId((currentSelectedSubscriberId) => {
      if (
        currentSelectedSubscriberId &&
        subscribers.some((subscriber) => subscriber.id === currentSelectedSubscriberId)
      ) {
        return currentSelectedSubscriberId;
      }
      return subscribers[0]?.id ?? null;
    });
  }, [subscribers]);

  const selectedSubscriber = useMemo(
    () =>
      subscribers.find((subscriber) => subscriber.id === selectedSubscriberId) ??
      subscribers[0] ??
      null,
    [selectedSubscriberId, subscribers],
  );
  const selectedSubscriberCards = useMemo(() => {
    if (!selectedSubscriber) {
      return [];
    }

    return [
      {
        label: "Subscriber identity",
        value: selectedSubscriber.full_name,
        note: `${formatStatusLabel(selectedSubscriber.consumer_type)} • ${selectedSubscriber.id}`,
      },
      {
        label: "Commercial posture",
        value: buildCommercialPosture(selectedSubscriber),
        note:
          selectedSubscriber.primary_account_number ??
          selectedSubscriber.primary_service_point_code ??
          "No primary account or service cue visible",
      },
      {
        label: "Primary account cue",
        value: selectedSubscriber.primary_account_number ?? "No linked account",
        note:
          selectedSubscriber.account_status_summary !== null
            ? formatStatusLabel(selectedSubscriber.account_status_summary)
            : "No active account summary recorded",
      },
      {
        label: "Service context",
        value: selectedSubscriber.primary_service_point_code ?? "No linked service point",
        note:
          selectedSubscriber.primary_service_point_code
            ? "Primary install/premise cue is visible in the list result"
            : "No primary service-point cue is visible in the list result",
      },
      {
        label: "Operational linkage",
        value: `${selectedSubscriber.linked_meter_count} meter(s)`,
        note: `${selectedSubscriber.active_account_count} active account(s)`,
      },
      {
        label: "Identifiers",
        value: buildIdentifierSummary(selectedSubscriber),
        note:
          selectedSubscriber.external_ref && selectedSubscriber.national_id
            ? "External reference and national ID are both available"
            : "Bounded subscriber identifier visibility",
      },
    ];
  }, [selectedSubscriber]);
  const selectedSubscriberNarrative = useMemo(() => {
    if (!selectedSubscriber) {
      return null;
    }

    return `${formatStatusLabel(selectedSubscriber.consumer_type)} subscriber ${selectedSubscriber.full_name} has ${formatCountLabel(
      selectedSubscriber.active_account_count,
      "active account",
      "active accounts",
    )} and ${formatCountLabel(
      selectedSubscriber.linked_meter_count,
      "linked meter",
      "linked meters",
    )} visible before opening the detail route${
      selectedSubscriber.primary_account_number
        ? `, with account ${selectedSubscriber.primary_account_number} in immediate scope.`
        : "."
    }`;
  }, [selectedSubscriber]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}

      <div className="detail-stack">
        <section className="subpanel subscribers-overview-panel">
          <div className="section-heading">
            <div>
              <h2>Subscriber operations center</h2>
              <p className="muted">
                Bounded visibility into subscriber identity, linked account context,
                and operational meter linkage.
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
                placeholder="Name, external reference, or national ID"
              />
            </label>
            <button
              className="primary-button"
              disabled={isLoadingSubscribers}
              type="submit"
            >
              {isLoadingSubscribers ? "Loading..." : "Load subscribers"}
            </button>
          </form>

          {isLoadingSubscribers ? (
            <p className="muted">Loading subscribers...</p>
          ) : (
            <div className="subscribers-overview-grid">
              {overviewCards.map((card) => (
                <div key={card.label} className="stat-card subscribers-overview-card">
                  <span className="stat-label">{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="subscribers-module-layout">
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Subscriber list</h2>
                <p className="muted">
                  Browse the existing subscriber surface and keep direct drill-down into
                  bounded detail routes.
                </p>
              </div>
            </div>

            <div className="meter-list">
              {!isLoadingSubscribers && subscribers.length === 0 ? (
                <p className="muted">No subscribers available for the current query.</p>
              ) : null}

              {subscribers.map((subscriber) => (
                <div
                  key={subscriber.id}
                  className={`meter-list-item subscriber-list-item${
                    selectedSubscriber?.id === subscriber.id ? " selected" : ""
                  }`}
                >
                  <div className="command-list-item-header">
                    <strong>{subscriber.full_name}</strong>
                    <span
                      className={`status-pill ${buildStatusTone(
                        subscriber.account_status_summary,
                      )}`}
                    >
                      {formatStatusLabel(subscriber.account_status_summary ?? "unassigned")}
                    </span>
                  </div>
                  <div className="command-list-item-badges">
                    <span
                      className={`status-pill ${buildStatusTone(
                        buildCommercialPosture(subscriber),
                      )}`}
                    >
                      {buildCommercialPosture(subscriber)}
                    </span>
                    <span className="artifact-pill">
                      {formatStatusLabel(subscriber.consumer_type)}
                    </span>
                    <span className="artifact-pill">
                      {subscriber.primary_account_number
                        ? `Account ${subscriber.primary_account_number}`
                        : "No linked account"}
                    </span>
                    <span className="artifact-pill">
                      {subscriber.primary_service_point_code
                        ? `Service point ${subscriber.primary_service_point_code}`
                        : "No linked service point"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Consumer ID {subscriber.id}</span>
                    <span>
                      {subscriber.external_ref ??
                        subscriber.national_id ??
                        "No key external identifier"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{subscriber.linked_meter_count} linked meter(s)</span>
                    <span>{subscriber.active_account_count} active account(s)</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>{buildIdentifierSummary(subscriber)}</span>
                    <span>
                      {subscriber.primary_account_number
                        ? "Account context ready"
                        : "No account context"}
                    </span>
                  </div>
                  <div className="artifact-row">
                    <button
                      className="secondary-button"
                      onClick={() => setSelectedSubscriberId(subscriber.id)}
                      type="button"
                    >
                      Inspect summary
                    </button>
                    <Link
                      className="secondary-button"
                      href={`/subscribers/${subscriber.id}`}
                    >
                      Open subscriber detail
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h2>Selected subscriber summary</h2>
                <p className="muted">
                  Bounded inline review of identity, account linkage, and service context
                  before opening the existing subscriber detail route.
                </p>
              </div>
              {selectedSubscriber ? (
                <span
                  className={`status-pill ${buildStatusTone(
                    selectedSubscriber.account_status_summary,
                  )}`}
                >
                  {formatStatusLabel(
                    selectedSubscriber.account_status_summary ?? "unassigned",
                  )}
                </span>
              ) : null}
            </div>

            {isLoadingSubscribers ? (
              <p className="muted">Loading selected subscriber summary...</p>
            ) : selectedSubscriber ? (
              <div className="detail-stack">
                <section className="subscriber-detail-hero">
                  <div className="subscriber-detail-title-row">
                    <div>
                      <p className="eyebrow">Selected Subscriber</p>
                      <h3>{selectedSubscriber.full_name}</h3>
                      <p className="muted">
                        {formatStatusLabel(selectedSubscriber.consumer_type)} subscriber with{" "}
                        {selectedSubscriber.active_account_count} active account(s) and{" "}
                        {selectedSubscriber.linked_meter_count} linked meter(s).
                      </p>
                    </div>
                    <span
                      className={`status-pill ${buildStatusTone(
                        selectedSubscriber.account_status_summary,
                      )}`}
                    >
                      {formatStatusLabel(
                        selectedSubscriber.account_status_summary ?? "unassigned",
                      )}
                    </span>
                  </div>

                  <div className="command-list-item-badges">
                    <span className="artifact-pill">
                      {selectedSubscriber.external_ref ??
                        selectedSubscriber.national_id ??
                        "No external identifier"}
                    </span>
                    <span className="artifact-pill">
                      {selectedSubscriber.primary_account_number
                        ? `Account ${selectedSubscriber.primary_account_number}`
                        : "No linked account"}
                    </span>
                    <span className="artifact-pill">
                      {selectedSubscriber.primary_service_point_code
                        ? `Service point ${selectedSubscriber.primary_service_point_code}`
                        : "No linked service point"}
                    </span>
                  </div>
                </section>

                {selectedSubscriberNarrative ? (
                  <p className="muted">{selectedSubscriberNarrative}</p>
                ) : null}

                <div className="artifact-row">
                  <span className="artifact-pill">
                    {buildCommercialPosture(selectedSubscriber)}
                  </span>
                  <span className="artifact-pill">
                    {formatStatusLabel(selectedSubscriber.consumer_type)}
                  </span>
                  <span className="artifact-pill">
                    {selectedSubscriber.primary_account_number
                      ? `Account ${selectedSubscriber.primary_account_number}`
                      : "No linked account"}
                  </span>
                  <span className="artifact-pill">
                    {selectedSubscriber.primary_service_point_code
                      ? `Service point ${selectedSubscriber.primary_service_point_code}`
                      : "No linked service point"}
                  </span>
                </div>

                <div className="detail-grid">
                  {selectedSubscriberCards.map((card) => (
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
                    href={`/subscribers/${selectedSubscriber.id}`}
                  >
                    Open subscriber detail
                  </Link>
                </div>
              </div>
            ) : (
              <p className="muted">No subscriber selected for bounded summary review.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
