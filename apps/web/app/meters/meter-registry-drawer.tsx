"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../session-provider";

export type MeterRegistryRow = {
  id: string;
  serial_number: string;
  utility_meter_number: string | null;
  badge_number: string | null;
  manufacturer_id: string;
  manufacturer_code: string;
  meter_model_id: string;
  meter_model_code: string;
  firmware_version_id: string | null;
  firmware_version: string | null;
  communication_profile_id: string | null;
  communication_profile_code: string | null;
  meter_profile_id: string | null;
  meter_profile_code: string | null;
  current_status: string;
  notes: string | null;
  is_active: boolean;
};

type CatalogManufacturer = { id: string; code: string; name: string };
type CatalogModel = {
  id: string;
  manufacturer_id: string;
  model_code: string;
  display_name: string;
};
type CatalogFirmware = { id: string; meter_model_id: string; version: string };
type CatalogComm = { id: string; code: string; name: string };
type CatalogMeterProfile = {
  id: string;
  meter_model_id: string;
  code: string;
  name: string;
};

const LIFECYCLE_VALUES = [
  "registered",
  "commissioned",
  "active",
  "inactive",
  "retired",
] as const;

function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

export type RegistryDrawerMode = "create" | "edit" | "lifecycle" | "toggle-active";

type MeterRegistryDrawerProps = {
  open: boolean;
  mode: RegistryDrawerMode;
  meter: MeterRegistryRow | null;
  onClose: () => void;
  onSuccess: () => void;
  authorizedFetch: AuthorizedFetch;
};

export function MeterRegistryDrawer({
  open,
  mode,
  meter,
  onClose,
  onSuccess,
  authorizedFetch,
}: MeterRegistryDrawerProps) {
  const [manufacturers, setManufacturers] = useState<CatalogManufacturer[]>([]);
  const [models, setModels] = useState<CatalogModel[]>([]);
  const [firmware, setFirmware] = useState<CatalogFirmware[]>([]);
  const [commProfiles, setCommProfiles] = useState<CatalogComm[]>([]);
  const [meterProfiles, setMeterProfiles] = useState<CatalogMeterProfile[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [serial, setSerial] = useState("");
  const [manufacturerId, setManufacturerId] = useState("");
  const [modelId, setModelId] = useState("");
  const [utility, setUtility] = useState("");
  const [badge, setBadge] = useState("");
  const [firmwareId, setFirmwareId] = useState("");
  const [commId, setCommId] = useState("");
  const [profileId, setProfileId] = useState("");
  const [createStatus, setCreateStatus] = useState<string>("registered");
  const [notes, setNotes] = useState("");
  const [isActive, setIsActive] = useState(true);

  const [lifecycleTarget, setLifecycleTarget] = useState<string>("active");
  const [lifecycleReason, setLifecycleReason] = useState("");

  const loadCatalogs = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const [mRes, modRes, fwRes, cRes, pRes] = await Promise.all([
        authorizedFetch<{ items: CatalogManufacturer[] }>("/api/v1/manufacturers"),
        authorizedFetch<{ items: CatalogModel[] }>("/api/v1/models"),
        authorizedFetch<{ items: CatalogFirmware[] }>("/api/v1/firmware-versions"),
        authorizedFetch<{ items: CatalogComm[] }>("/api/v1/communication-profiles"),
        authorizedFetch<{ items: CatalogMeterProfile[] }>("/api/v1/meter-profiles"),
      ]);
      setManufacturers(mRes.items ?? []);
      setModels(modRes.items ?? []);
      setFirmware(fwRes.items ?? []);
      setCommProfiles(cRes.items ?? []);
      setMeterProfiles(pRes.items ?? []);
    } catch (e) {
      setCatalogError(e instanceof Error ? e.message : "Catalog load failed.");
    } finally {
      setCatalogLoading(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    if (!open) {
      return;
    }
    if (mode === "create" || mode === "edit") {
      void loadCatalogs();
    }
  }, [open, mode, loadCatalogs]);

  useEffect(() => {
    if (!open || !meter) {
      return;
    }
    if (mode === "edit") {
      setUtility(meter.utility_meter_number ?? "");
      setBadge(meter.badge_number ?? "");
      setFirmwareId(meter.firmware_version_id ?? "");
      setCommId(meter.communication_profile_id ?? "");
      setProfileId(meter.meter_profile_id ?? "");
      setNotes(meter.notes ?? "");
      setIsActive(meter.is_active);
    }
    if (mode === "lifecycle") {
      const next =
        LIFECYCLE_VALUES.find((v) => v !== meter.current_status) ?? "inactive";
      setLifecycleTarget(next);
      setLifecycleReason("");
    }
  }, [open, mode, meter]);

  useEffect(() => {
    if (!open || mode !== "create") {
      return;
    }
    setSerial("");
    setManufacturerId("");
    setModelId("");
    setUtility("");
    setBadge("");
    setFirmwareId("");
    setCommId("");
    setProfileId("");
    setCreateStatus("registered");
    setNotes("");
    setSubmitError(null);
  }, [open, mode]);

  const filteredModels = useMemo(
    () => models.filter((m) => !manufacturerId || m.manufacturer_id === manufacturerId),
    [manufacturerId, models],
  );

  const filteredFirmware = useMemo(
    () => firmware.filter((f) => !modelId || f.meter_model_id === modelId),
    [firmware, modelId],
  );

  const filteredMeterProfiles = useMemo(
    () => meterProfiles.filter((p) => !modelId || p.meter_model_id === modelId),
    [meterProfiles, modelId],
  );

  useEffect(() => {
    if (modelId && !filteredModels.some((m) => m.id === modelId)) {
      setModelId("");
      setFirmwareId("");
      setProfileId("");
    }
  }, [filteredModels, modelId]);

  const title =
    mode === "create"
      ? "Add meter"
      : mode === "edit"
        ? "Edit registry"
        : mode === "lifecycle"
          ? "Change lifecycle"
          : meter?.is_active
            ? "Set inactive"
            : "Set active";

  const handleSubmitCreate = async () => {
    if (!serial.trim() || !manufacturerId || !modelId) {
      setSubmitError("Serial, manufacturer, and model are required.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body: Record<string, unknown> = {
        serial_number: serial.trim(),
        manufacturer_id: manufacturerId,
        meter_model_id: modelId,
        current_status: createStatus,
        is_active: true,
      };
      if (utility.trim()) {
        body.utility_meter_number = utility.trim();
      }
      if (badge.trim()) {
        body.badge_number = badge.trim();
      }
      if (firmwareId) {
        body.firmware_version_id = firmwareId;
      }
      if (commId) {
        body.communication_profile_id = commId;
      }
      if (profileId) {
        body.meter_profile_id = profileId;
      }
      if (notes.trim()) {
        body.notes = notes.trim();
      }
      await authorizedFetch("/api/v1/meters", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onSuccess();
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Create failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitEdit = async () => {
    if (!meter) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const body: Record<string, unknown> = {
        utility_meter_number: utility.trim() ? utility.trim() : null,
        badge_number: badge.trim() ? badge.trim() : null,
        firmware_version_id: firmwareId || null,
        communication_profile_id: commId || null,
        meter_profile_id: profileId || null,
        notes: notes.trim() ? notes.trim() : null,
        is_active: isActive,
      };
      await authorizedFetch(`/api/v1/meters/${meter.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      onSuccess();
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitLifecycle = async () => {
    if (!meter) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await authorizedFetch(`/api/v1/meters/${meter.id}/status`, {
        method: "POST",
        body: JSON.stringify({
          new_status: lifecycleTarget,
          reason: lifecycleReason.trim() || null,
        }),
      });
      onSuccess();
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Status change failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitToggleActive = async () => {
    if (!meter) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await authorizedFetch(`/api/v1/meters/${meter.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !meter.is_active }),
      });
      onSuccess();
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Update failed.");
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="ws-drawer-root" role="presentation">
      <button
        type="button"
        className="ws-drawer-backdrop"
        aria-label="Close panel"
        onClick={onClose}
      />
      <div
        className="ws-drawer-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ws-drawer-title"
      >
        <div className="ws-drawer-head">
          <h2 id="ws-drawer-title" className="ws-drawer-title">
            {title}
          </h2>
          <button type="button" className="ws-drawer-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="ws-drawer-body">
          {catalogError ? (
            <p className="ws-drawer-banner" role="alert">
              {catalogError}
            </p>
          ) : null}
          {submitError ? (
            <p className="ws-drawer-banner" role="alert">
              {submitError}
            </p>
          ) : null}

          {mode === "create" ? (
            <>
              {catalogLoading ? <p className="ws-muted">Loading catalogs…</p> : null}
              <div className="ws-drawer-fields">
                <label className="ws-drawer-field">
                  <span>Serial number</span>
                  <input
                    value={serial}
                    onChange={(e) => setSerial(e.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="ws-drawer-field">
                  <span>Manufacturer</span>
                  <select
                    value={manufacturerId}
                    onChange={(e) => {
                      setManufacturerId(e.target.value);
                      setModelId("");
                      setFirmwareId("");
                      setProfileId("");
                    }}
                  >
                    <option value="">Select…</option>
                    {manufacturers.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.code} — {m.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Model</span>
                  <select
                    value={modelId}
                    onChange={(e) => {
                      setModelId(e.target.value);
                      setFirmwareId("");
                      setProfileId("");
                    }}
                    disabled={!manufacturerId}
                  >
                    <option value="">Select…</option>
                    {filteredModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.model_code}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Utility meter number</span>
                  <input value={utility} onChange={(e) => setUtility(e.target.value)} />
                </label>
                <label className="ws-drawer-field">
                  <span>Badge number</span>
                  <input value={badge} onChange={(e) => setBadge(e.target.value)} />
                </label>
                <label className="ws-drawer-field">
                  <span>Firmware</span>
                  <select
                    value={firmwareId}
                    onChange={(e) => setFirmwareId(e.target.value)}
                    disabled={!modelId}
                  >
                    <option value="">None</option>
                    {filteredFirmware.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.version}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Communication profile</span>
                  <select value={commId} onChange={(e) => setCommId(e.target.value)}>
                    <option value="">None</option>
                    {commProfiles.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Meter profile</span>
                  <select
                    value={profileId}
                    onChange={(e) => setProfileId(e.target.value)}
                    disabled={!modelId}
                  >
                    <option value="">None</option>
                    {filteredMeterProfiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Initial lifecycle</span>
                  <select
                    value={createStatus}
                    onChange={(e) => setCreateStatus(e.target.value)}
                  >
                    {LIFECYCLE_VALUES.map((v) => (
                      <option key={v} value={v}>
                        {humanize(v)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Notes</span>
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
                </label>
              </div>
              <div className="ws-drawer-footer">
                <button type="button" className="ws-btn ws-btn-ghost" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="ws-btn ws-btn-primary"
                  disabled={submitting || catalogLoading}
                  onClick={() => void handleSubmitCreate()}
                >
                  Create meter
                </button>
              </div>
            </>
          ) : null}

          {mode === "edit" && meter ? (
            <>
              {catalogLoading ? <p className="ws-muted">Loading catalogs…</p> : null}
              <p className="ws-drawer-meta">
                <span className="ws-meters-mono">{meter.serial_number}</span>
                <span className="ws-drawer-meta-sep">·</span>
                {meter.manufacturer_code} / {meter.meter_model_code}
              </p>
              <div className="ws-drawer-fields">
                <label className="ws-drawer-field">
                  <span>Utility meter number</span>
                  <input value={utility} onChange={(e) => setUtility(e.target.value)} />
                </label>
                <label className="ws-drawer-field">
                  <span>Badge number</span>
                  <input value={badge} onChange={(e) => setBadge(e.target.value)} />
                </label>
                <label className="ws-drawer-field">
                  <span>Firmware</span>
                  <select value={firmwareId} onChange={(e) => setFirmwareId(e.target.value)}>
                    <option value="">None</option>
                    {firmware
                      .filter((f) => f.meter_model_id === meter.meter_model_id)
                      .map((f) => (
                        <option key={f.id} value={f.id}>
                          {f.version}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Communication profile</span>
                  <select value={commId} onChange={(e) => setCommId(e.target.value)}>
                    <option value="">None</option>
                    {commProfiles.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Meter profile</span>
                  <select value={profileId} onChange={(e) => setProfileId(e.target.value)}>
                    <option value="">None</option>
                    {meterProfiles
                      .filter((p) => p.meter_model_id === meter.meter_model_id)
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.code}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="ws-drawer-field ws-drawer-field--check">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  <span>Active in registry</span>
                </label>
                <label className="ws-drawer-field">
                  <span>Notes</span>
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
                </label>
              </div>
              <div className="ws-drawer-footer">
                <button type="button" className="ws-btn ws-btn-ghost" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="ws-btn ws-btn-primary"
                  disabled={submitting || catalogLoading}
                  onClick={() => void handleSubmitEdit()}
                >
                  Save changes
                </button>
              </div>
            </>
          ) : null}

          {mode === "lifecycle" && meter ? (
            <>
              <p className="ws-drawer-meta">
                Current: <strong>{humanize(meter.current_status)}</strong>
              </p>
              <div className="ws-drawer-fields">
                <label className="ws-drawer-field">
                  <span>New lifecycle status</span>
                  <select
                    value={lifecycleTarget}
                    onChange={(e) => setLifecycleTarget(e.target.value)}
                  >
                    {(LIFECYCLE_VALUES.filter((v) => v !== meter.current_status).length
                      ? LIFECYCLE_VALUES.filter((v) => v !== meter.current_status)
                      : [...LIFECYCLE_VALUES]
                    ).map((v) => (
                      <option key={v} value={v}>
                        {humanize(v)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ws-drawer-field">
                  <span>Reason (optional)</span>
                  <textarea
                    value={lifecycleReason}
                    onChange={(e) => setLifecycleReason(e.target.value)}
                    rows={3}
                  />
                </label>
              </div>
              <div className="ws-drawer-footer">
                <button type="button" className="ws-btn ws-btn-ghost" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="ws-btn ws-btn-secondary"
                  disabled={submitting}
                  onClick={() => void handleSubmitLifecycle()}
                >
                  Apply lifecycle change
                </button>
              </div>
            </>
          ) : null}

          {mode === "toggle-active" && meter ? (
            <>
              <p className="ws-drawer-meta">
                {meter.is_active
                  ? "This meter will be marked inactive in the registry."
                  : "This meter will be marked active in the registry."}
              </p>
              <div className="ws-drawer-footer">
                <button type="button" className="ws-btn ws-btn-ghost" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="ws-btn ws-btn-secondary"
                  disabled={submitting}
                  onClick={() => void handleSubmitToggleActive()}
                >
                  Confirm
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
