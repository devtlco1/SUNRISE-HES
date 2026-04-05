"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { REGISTRY_PAGE_LIMITS, RegistryPager } from "../registry-pagination";
import { useSession } from "../session-provider";
import { WorkspaceShell } from "../workspace-shell";

const READINGS_PER_METER = 50;

type MeterRow = {
  id: string;
  serial_number: string;
};

type MeterListResponse = { total: number; items: MeterRow[] };

type MeterReading = {
  id: string;
  batch_id: string;
  meter_id: string;
  obis_code: string;
  reading_type: string;
  value_numeric: string | number | null;
  value_text: string | null;
  value_timestamp: string | null;
  unit: string | null;
  quality: string | null;
  captured_at: string;
  metadata: Record<string, unknown> | null;
};

type MeterReadingListResponse = { total: number; items: MeterReading[] };

type ReadingRow = MeterReading & { meter_serial: string };

type KpiAccent = "neutral" | "success" | "danger" | "warning" | "info" | "muted";

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

function fmtWhen(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function fmtAsOf(iso: string | null): string {
  if (!iso) {
    return "";
  }
  try {
    return new Date(iso).toLocaleString("en-US", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

function formatValue(r: MeterReading): string {
  if (r.value_numeric != null && r.value_numeric !== "") {
    const n = typeof r.value_numeric === "number" ? r.value_numeric : Number(r.value_numeric);
    if (!Number.isNaN(n)) {
      return r.unit ? `${n} ${r.unit}` : String(n);
    }
    return String(r.value_numeric);
  }
  if (r.value_text) {
    return r.value_text;
  }
  return "—";
}

function qualityAccent(q: string | null): KpiAccent {
  if (!q) {
    return "muted";
  }
  if (q === "good") {
    return "success";
  }
  if (q === "suspect" || q === "missing") {
    return q === "missing" ? "warning" : "danger";
  }
  if (q === "estimated") {
    return "info";
  }
  return "muted";
}

function toneCount(n: number, pos: KpiAccent): KpiAccent {
  return n > 0 ? pos : "muted";
}

type SummaryKpiProps = { label: string; value: string; accent: KpiAccent };

function SummaryKpi({ label, value, accent }: SummaryKpiProps) {
  return (
    <div className={`ws-kpi ws-kpi--accent-${accent}`} aria-label={label}>
      <div className="ws-kpi-label">{label}</div>
      <div className="ws-kpi-value">{value}</div>
    </div>
  );
}

const READING_TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "scalar", label: "Scalar" },
  { value: "register", label: "Register" },
  { value: "instantaneous", label: "Instantaneous" },
  { value: "demand", label: "Demand" },
];

const QUALITY_OPTIONS = [
  { value: "", label: "All quality" },
  { value: "good", label: "Good" },
  { value: "estimated", label: "Estimated" },
  { value: "suspect", label: "Suspect" },
  { value: "missing", label: "Missing" },
];

export function ReadingsPageClient() {
  return (
    <WorkspaceShell>
      <ReadingsBody />
    </WorkspaceShell>
  );
}

function ReadingsBody() {
  const { currentUser, isCheckingSession, authorizedFetch } = useSession();
  const [asOf, setAsOf] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metersTotal, setMetersTotal] = useState(0);
  const [meterLimit, setMeterLimit] = useState<(typeof REGISTRY_PAGE_LIMITS)[number]>(25);
  const [meterOffset, setMeterOffset] = useState(0);
  const [meterPage, setMeterPage] = useState<MeterRow[]>([]);
  const [readPageIdx, setReadPageIdx] = useState(0);
  const [readPageSize, setReadPageSize] = useState<(typeof REGISTRY_PAGE_LIMITS)[number]>(25);
  const [readingRows, setReadingRows] = useState<ReadingRow[]>([]);
  const [metersNoReads, setMetersNoReads] = useState<MeterRow[]>([]);

  const [typeFilter, setTypeFilter] = useState("");
  const [qualityFilter, setQualityFilter] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [searchApplied, setSearchApplied] = useState("");

  const load = useCallback(async () => {
    if (!currentUser) {
      return;
    }
    setLoading(true);
    setError(null);
    setAsOf(new Date().toISOString());
    try {
      const metersRes = await authorizedFetch<MeterListResponse>(
        `/api/v1/meters?limit=${meterLimit}&offset=${meterOffset}`,
      );
      setMetersTotal(metersRes.total);
      setMeterPage(metersRes.items);

      const serialById = new Map(metersRes.items.map((m) => [m.id, m.serial_number]));

      const settled = await Promise.allSettled(
        metersRes.items.map((m) =>
          authorizedFetch<MeterReadingListResponse>(`/api/v1/meters/${m.id}/readings?limit=${READINGS_PER_METER}`),
        ),
      );

      const rows: ReadingRow[] = [];
      const noReads: MeterRow[] = [];

      settled.forEach((res, i) => {
        const meter = metersRes.items[i]!;
        if (res.status !== "fulfilled") {
          return;
        }
        const data = res.value;
        if (data.total === 0 && data.items.length === 0) {
          noReads.push(meter);
        }
        for (const r of data.items) {
          rows.push({
            ...r,
            meter_serial: serialById.get(r.meter_id) ?? meter.serial_number,
          });
        }
      });

      rows.sort((a, b) => Date.parse(b.captured_at) - Date.parse(a.captured_at));
      setReadingRows(rows);
      setMetersNoReads(noReads);
    } catch (e) {
      setReadingRows([]);
      setMeterPage([]);
      setMetersNoReads([]);
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }, [authorizedFetch, currentUser, meterLimit, meterOffset]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    void load();
  }, [currentUser, load]);

  useEffect(() => {
    const t = window.setTimeout(() => setSearchApplied(searchDraft), 350);
    return () => window.clearTimeout(t);
  }, [searchDraft]);

  useEffect(() => {
    setReadPageIdx(0);
  }, [meterOffset, meterLimit, typeFilter, qualityFilter, searchApplied]);

  const kpi = useMemo(() => {
    const metersWithReads = new Set(readingRows.map((r) => r.meter_id)).size;
    const flagged = readingRows.filter((r) => r.quality === "suspect" || r.quality === "missing").length;
    const estimated = readingRows.filter((r) => r.quality === "estimated").length;
    const good = readingRows.filter((r) => r.quality === "good").length;
    return {
      readingsCount: readingRows.length,
      metersWithReads,
      withoutReads: metersNoReads.length,
      flagged,
      estimated,
      good,
    };
  }, [metersNoReads.length, readingRows]);

  const filteredReadings = useMemo(() => {
    const q = searchApplied.trim().toLowerCase();
    return readingRows.filter((r) => {
      if (typeFilter && r.reading_type !== typeFilter) {
        return false;
      }
      if (qualityFilter && r.quality !== qualityFilter) {
        return false;
      }
      if (!q) {
        return true;
      }
      return (
        r.meter_serial.toLowerCase().includes(q) ||
        r.obis_code.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q)
      );
    });
  }, [qualityFilter, readingRows, searchApplied, typeFilter]);

  const attentionMeters = useMemo(() => metersNoReads.slice(0, 14), [metersNoReads]);
  const attentionQuality = useMemo(
    () =>
      readingRows
        .filter((r) => r.quality === "suspect" || r.quality === "missing")
        .slice(0, 12),
    [readingRows],
  );

  const readTotal = filteredReadings.length;
  const readTotalPages = readTotal === 0 ? 0 : Math.ceil(readTotal / readPageSize);
  const readMaxPageIdx = Math.max(0, readTotalPages - 1);

  useEffect(() => {
    if (readPageIdx > readMaxPageIdx) {
      setReadPageIdx(readMaxPageIdx);
    }
  }, [readMaxPageIdx, readPageIdx]);

  const effectiveReadIdx = Math.min(readPageIdx, readMaxPageIdx);
  const pagedReadings = useMemo(() => {
    const start = effectiveReadIdx * readPageSize;
    return filteredReadings.slice(start, start + readPageSize);
  }, [effectiveReadIdx, filteredReadings, readPageSize]);

  const canMeterPrev = meterOffset > 0;
  const canMeterNext = meterOffset + meterPage.length < metersTotal;

  if (isCheckingSession) {
    return <p className="ws-muted">Checking session…</p>;
  }

  if (!currentUser) {
    return <p className="ws-muted">Sign in to view readings.</p>;
  }

  return (
    <div className="ws-canvas ws-read-page">
      <header className="ws-read-header">
        <div>
          <h1 className="ws-read-title">Readings</h1>
          <p className="ws-read-subtitle">Ingested register values, quality, and recency by meter.</p>
        </div>
        {asOf ? <p className="ws-muted ws-read-asof">As of {fmtAsOf(asOf)}</p> : null}
      </header>

      {error ? (
        <p className="ws-alert" role="alert">
          {error}
        </p>
      ) : null}

      <section className="ws-read-summary" aria-label="Readings summary">
        <div className="ws-kpi-grid ws-read-kpi-grid">
          <SummaryKpi label="Recent readings" value={loading && readingRows.length === 0 ? "—" : fmt(kpi.readingsCount)} accent="neutral" />
          <SummaryKpi
            label="Meters with readings"
            value={loading && readingRows.length === 0 ? "—" : fmt(kpi.metersWithReads)}
            accent={toneCount(kpi.metersWithReads, "success")}
          />
          <SummaryKpi
            label="Missing readings"
            value={loading ? "—" : fmt(kpi.withoutReads)}
            accent={toneCount(kpi.withoutReads, "warning")}
          />
          <SummaryKpi
            label="Flagged quality"
            value={loading && readingRows.length === 0 ? "—" : fmt(kpi.flagged)}
            accent={toneCount(kpi.flagged, "danger")}
          />
          <SummaryKpi
            label="Estimated"
            value={loading && readingRows.length === 0 ? "—" : fmt(kpi.estimated)}
            accent={toneCount(kpi.estimated, "info")}
          />
          <SummaryKpi
            label="Good quality"
            value={loading && readingRows.length === 0 ? "—" : fmt(kpi.good)}
            accent={toneCount(kpi.good, "success")}
          />
        </div>
      </section>

      <div className="ws-read-stack">
        <section className="ws-dash-panel ws-read-panel" aria-labelledby="read-overview-h">
          <h2 className="ws-dash-panel-title" id="read-overview-h">
            Readings overview
          </h2>
          <div className="ws-dash-panel-body ws-read-overview-body">
            {loading && meterPage.length === 0 ? (
              <p className="ws-muted">Loading…</p>
            ) : meterPage.length === 0 ? (
              <p className="ws-muted">Data not available yet.</p>
            ) : (
              <dl className="ws-read-dl">
                <div>
                  <dt>Listed readings</dt>
                  <dd>
                    <span className="ws-metric ws-metric--neutral">{fmt(kpi.readingsCount)}</span>
                  </dd>
                </div>
                <div>
                  <dt>Meters without reads</dt>
                  <dd>
                    <span className={`ws-metric ws-metric--${kpi.withoutReads > 0 ? "warning" : "muted"}`}>
                      {fmt(kpi.withoutReads)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Quality flags</dt>
                  <dd>
                    <span className={`ws-metric ws-metric--${kpi.flagged > 0 ? "danger" : "muted"}`}>
                      {fmt(kpi.flagged)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Estimated values</dt>
                  <dd>
                    <span className={`ws-metric ws-metric--${kpi.estimated > 0 ? "info" : "muted"}`}>
                      {fmt(kpi.estimated)}
                    </span>
                  </dd>
                </div>
              </dl>
            )}
          </div>
        </section>

        <section className="ws-dash-panel ws-read-panel" aria-labelledby="read-registry-h">
          <h2 className="ws-dash-panel-title" id="read-registry-h">
            Reading registry
          </h2>
          <div className="ws-dash-panel-body ws-read-registry-body">
            <div className="ws-read-toolbar">
              <div className="ws-read-toolbar-filters">
                <label className="ws-read-field">
                  <span className="ws-read-field-label">Type</span>
                  <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Reading type">
                    {READING_TYPE_OPTIONS.map((o) => (
                      <option key={o.value || "t-all"} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-read-field">
                  <span className="ws-read-field-label">Quality</span>
                  <select value={qualityFilter} onChange={(e) => setQualityFilter(e.target.value)} aria-label="Quality">
                    {QUALITY_OPTIONS.map((o) => (
                      <option key={o.value || "q-all"} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-read-field">
                  <span className="ws-read-field-label">Search</span>
                  <input
                    type="search"
                    value={searchDraft}
                    onChange={(e) => setSearchDraft(e.target.value)}
                    placeholder="Serial, OBIS, reading id…"
                    autoComplete="off"
                  />
                </label>
              </div>
              <div className="ws-read-toolbar-actions">
                <button type="button" className="ws-btn ws-btn-ghost" onClick={() => void load()} disabled={loading}>
                  Refresh
                </button>
              </div>
            </div>

            <RegistryPager
              disabled={loading}
              pageSize={meterLimit}
              onPageSizeChange={(n) => {
                setMeterLimit(n as (typeof REGISTRY_PAGE_LIMITS)[number]);
                setMeterOffset(0);
              }}
              rangeStart={metersTotal === 0 ? 0 : meterOffset + 1}
              rangeEnd={metersTotal === 0 ? 0 : meterOffset + meterPage.length}
              total={metersTotal}
              entityLabel="meters in scope"
              canPrev={canMeterPrev && !loading}
              canNext={canMeterNext && !loading}
              onPrev={() => setMeterOffset((o) => Math.max(0, o - meterLimit))}
              onNext={() => setMeterOffset((o) => o + meterLimit)}
            />

            {loading && readingRows.length === 0 ? (
              <p className="ws-muted">Loading…</p>
            ) : (
              <>
                <div className="ws-read-table-wrap">
                  <table className="ws-read-table">
                    <thead>
                      <tr>
                        <th scope="col">Meter</th>
                        <th scope="col">OBIS</th>
                        <th scope="col">Type</th>
                        <th scope="col">Value</th>
                        <th scope="col">Quality</th>
                        <th scope="col">Captured</th>
                        <th scope="col">Reading time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredReadings.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="ws-read-table-empty">
                            No readings found.
                          </td>
                        </tr>
                      ) : (
                        pagedReadings.map((r) => (
                          <tr key={r.id}>
                            <td>
                              <Link className="ws-meters-drilldown" href={`/meters/${r.meter_id}`} title={r.meter_id}>
                                {r.meter_serial}
                              </Link>
                            </td>
                            <td className="ws-read-mono">{r.obis_code}</td>
                            <td>{humanize(r.reading_type)}</td>
                            <td className="ws-read-mono">{formatValue(r)}</td>
                            <td>
                              <span className={`ws-metric ws-metric--${qualityAccent(r.quality)}`}>
                                {r.quality ? humanize(r.quality) : "—"}
                              </span>
                            </td>
                            <td className="ws-read-mono">{fmtWhen(r.captured_at)}</td>
                            <td className="ws-read-mono">{fmtWhen(r.value_timestamp)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                <RegistryPager
                  disabled={loading}
                  pageSize={readPageSize}
                  onPageSizeChange={(n) => {
                    setReadPageSize(n as (typeof REGISTRY_PAGE_LIMITS)[number]);
                    setReadPageIdx(0);
                  }}
                  rangeStart={readTotal === 0 ? 0 : effectiveReadIdx * readPageSize + 1}
                  rangeEnd={readTotal === 0 ? 0 : Math.min((effectiveReadIdx + 1) * readPageSize, readTotal)}
                  total={readTotal}
                  entityLabel="readings"
                  canPrev={readTotal > 0 && effectiveReadIdx > 0}
                  canNext={readTotal > 0 && effectiveReadIdx < readMaxPageIdx}
                  onPrev={() => setReadPageIdx((i) => Math.max(0, i - 1))}
                  onNext={() => setReadPageIdx((i) => Math.min(readMaxPageIdx, i + 1))}
                />
              </>
            )}
          </div>
        </section>

        <section className="ws-dash-panel ws-read-panel" aria-labelledby="read-attention-h">
          <h2 className="ws-dash-panel-title" id="read-attention-h">
            Attention
          </h2>
          <div className="ws-dash-panel-body ws-read-attention-body">
            {attentionMeters.length === 0 && attentionQuality.length === 0 ? (
              <p className="ws-muted">No meters need attention.</p>
            ) : (
              <div className="ws-read-attention-cols">
                {attentionMeters.length > 0 ? (
                  <div className="ws-read-attention-block">
                    <h3 className="ws-read-attention-subh">Meters without readings</h3>
                    <div className="ws-read-table-wrap">
                      <table className="ws-read-table ws-read-table--compact">
                        <thead>
                          <tr>
                            <th scope="col">Meter</th>
                            <th scope="col">Issue</th>
                          </tr>
                        </thead>
                        <tbody>
                          {attentionMeters.map((m) => (
                            <tr key={m.id}>
                              <td>
                                <Link className="ws-meters-drilldown" href={`/meters/${m.id}`}>
                                  {m.serial_number}
                                </Link>
                              </td>
                              <td>
                                <span className="ws-metric ws-metric--warning">No ingested reads</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}
                {attentionQuality.length > 0 ? (
                  <div className="ws-read-attention-block">
                    <h3 className="ws-read-attention-subh">Quality flags</h3>
                    <div className="ws-read-table-wrap">
                      <table className="ws-read-table ws-read-table--compact">
                        <thead>
                          <tr>
                            <th scope="col">Meter</th>
                            <th scope="col">OBIS</th>
                            <th scope="col">Quality</th>
                          </tr>
                        </thead>
                        <tbody>
                          {attentionQuality.map((r) => (
                            <tr key={`q-${r.id}`}>
                              <td>
                                <Link className="ws-meters-drilldown" href={`/meters/${r.meter_id}`}>
                                  {r.meter_serial}
                                </Link>
                              </td>
                              <td className="ws-read-mono">{r.obis_code}</td>
                              <td>
                                <span className={`ws-metric ws-metric--${qualityAccent(r.quality)}`}>
                                  {r.quality ? humanize(r.quality) : "—"}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
