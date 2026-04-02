"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AuthorizedFetch } from "../../operational-shell";

type MeterManufacturer = {
  id: string;
  code: string;
  name: string;
};

type MeterManufacturerListResponse = {
  total: number;
  items: MeterManufacturer[];
};

type MeterModel = {
  id: string;
  manufacturer_id: string;
  manufacturer_code: string;
  model_code: string;
  display_name: string;
};

type MeterModelListResponse = {
  total: number;
  items: MeterModel[];
};

type MeterCreateResponse = {
  id: string;
  serial_number: string;
};

type PreviewRow = {
  lineNumber: number;
  serialNumber: string;
  utilityMeterNumber: string | null;
  manufacturerCode: string;
  meterModelCode: string;
  currentStatus: string;
  manufacturerId: string | null;
  meterModelId: string | null;
  errors: string[];
};

type ImportResult = {
  lineNumber: number;
  serialNumber: string;
  status: "imported" | "skipped";
  detail: string;
  createdMeterId: string | null;
};

const REQUIRED_HEADERS = ["serial_number", "manufacturer_code", "meter_model_code"] as const;
const OPTIONAL_HEADERS = ["utility_meter_number", "current_status"] as const;
const SUPPORTED_HEADERS = [...REQUIRED_HEADERS, ...OPTIONAL_HEADERS];
const SUPPORTED_HEADERS_SET = new Set<string>(SUPPORTED_HEADERS);
const SUPPORTED_STATUSES = new Set([
  "registered",
  "commissioned",
  "active",
  "inactive",
  "retired",
]);

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let currentValue = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    const nextCharacter = line[index + 1];

    if (character === '"') {
      if (inQuotes && nextCharacter === '"') {
        currentValue += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (character === "," && !inQuotes) {
      values.push(currentValue.trim());
      currentValue = "";
      continue;
    }

    currentValue += character;
  }

  values.push(currentValue.trim());
  return values;
}

function normalizeCode(value: string): string {
  return value.trim().toLowerCase();
}

function buildPreviewRows(
  csvText: string,
  manufacturers: MeterManufacturer[],
  meterModels: MeterModel[],
): {
  previewRows: PreviewRow[];
  recognizedHeaders: string[];
  ignoredHeaders: string[];
  parseError: string | null;
} {
  const normalizedText = csvText.replace(/^\ufeff/, "").trim();
  if (!normalizedText) {
    return {
      previewRows: [],
      recognizedHeaders: [],
      ignoredHeaders: [],
      parseError: "CSV file is empty.",
    };
  }

  const nonEmptyLines = normalizedText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (nonEmptyLines.length <= 1) {
    return {
      previewRows: [],
      recognizedHeaders: [],
      ignoredHeaders: [],
      parseError: "CSV file does not contain any meter rows.",
    };
  }

  const headers = parseCsvLine(nonEmptyLines[0]).map((header) => normalizeCode(header));
  const recognizedHeaders = headers.filter((header) => SUPPORTED_HEADERS_SET.has(header));
  const ignoredHeaders = headers.filter((header) => !SUPPORTED_HEADERS_SET.has(header));
  const missingRequiredHeaders = REQUIRED_HEADERS.filter((header) => !headers.includes(header));
  if (missingRequiredHeaders.length > 0) {
    return {
      previewRows: [],
      recognizedHeaders,
      ignoredHeaders,
      parseError: `Required CSV columns are missing: ${missingRequiredHeaders.join(", ")}.`,
    };
  }

  const manufacturersByCode = new Map(
    manufacturers.map((manufacturer) => [normalizeCode(manufacturer.code), manufacturer]),
  );
  const meterModelsByManufacturerAndCode = new Map(
    meterModels.map((meterModel) => [
      `${meterModel.manufacturer_id}:${normalizeCode(meterModel.model_code)}`,
      meterModel,
    ]),
  );

  const rawRows = nonEmptyLines.slice(1).map((line, index) => {
    const values = parseCsvLine(line);
    const rowData = Object.fromEntries(headers.map((header, headerIndex) => [header, values[headerIndex] ?? ""]));
    return {
      lineNumber: index + 2,
      serialNumber: rowData.serial_number?.trim() ?? "",
      utilityMeterNumber: rowData.utility_meter_number?.trim() || null,
      manufacturerCode: normalizeCode(rowData.manufacturer_code ?? ""),
      meterModelCode: normalizeCode(rowData.meter_model_code ?? ""),
      currentStatus: normalizeCode(rowData.current_status ?? "") || "registered",
    };
  });

  const serialCounts = new Map<string, number>();
  const utilityCounts = new Map<string, number>();
  rawRows.forEach((row) => {
    if (row.serialNumber) {
      serialCounts.set(row.serialNumber.toLowerCase(), (serialCounts.get(row.serialNumber.toLowerCase()) ?? 0) + 1);
    }
    if (row.utilityMeterNumber) {
      utilityCounts.set(
        row.utilityMeterNumber.toLowerCase(),
        (utilityCounts.get(row.utilityMeterNumber.toLowerCase()) ?? 0) + 1,
      );
    }
  });

  const previewRows = rawRows.map((row) => {
    const errors: string[] = [];

    if (!row.serialNumber) {
      errors.push("Serial number is required.");
    }
    if (!row.manufacturerCode) {
      errors.push("Manufacturer code is required.");
    }
    if (!row.meterModelCode) {
      errors.push("Meter model code is required.");
    }
    if (!SUPPORTED_STATUSES.has(row.currentStatus)) {
      errors.push("Current status must be one of registered, commissioned, active, inactive, or retired.");
    }
    if (row.serialNumber && (serialCounts.get(row.serialNumber.toLowerCase()) ?? 0) > 1) {
      errors.push("Serial number is duplicated within this CSV file.");
    }
    if (
      row.utilityMeterNumber &&
      (utilityCounts.get(row.utilityMeterNumber.toLowerCase()) ?? 0) > 1
    ) {
      errors.push("Utility meter number is duplicated within this CSV file.");
    }

    const manufacturer = row.manufacturerCode
      ? manufacturersByCode.get(row.manufacturerCode) ?? null
      : null;
    if (row.manufacturerCode && manufacturer === null) {
      errors.push("Manufacturer code is not available in the current device catalog.");
    }

    const meterModel =
      manufacturer !== null
        ? meterModelsByManufacturerAndCode.get(`${manufacturer.id}:${row.meterModelCode}`) ?? null
        : null;
    if (manufacturer !== null && row.meterModelCode && meterModel === null) {
      errors.push("Meter model code is not available for the selected manufacturer.");
    }

    return {
      lineNumber: row.lineNumber,
      serialNumber: row.serialNumber,
      utilityMeterNumber: row.utilityMeterNumber,
      manufacturerCode: row.manufacturerCode,
      meterModelCode: row.meterModelCode,
      currentStatus: row.currentStatus,
      manufacturerId: manufacturer?.id ?? null,
      meterModelId: meterModel?.id ?? null,
      errors,
    };
  });

  return {
    previewRows,
    recognizedHeaders,
    ignoredHeaders,
    parseError: null,
  };
}

export function MeterImportModule({
  authorizedFetch,
}: {
  authorizedFetch: AuthorizedFetch;
}) {
  const [manufacturers, setManufacturers] = useState<MeterManufacturer[]>([]);
  const [meterModels, setMeterModels] = useState<MeterModel[]>([]);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [recognizedHeaders, setRecognizedHeaders] = useState<string[]>([]);
  const [ignoredHeaders, setIgnoredHeaders] = useState<string[]>([]);
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  const [importResults, setImportResults] = useState<ImportResult[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);
  const [isSubmittingImport, setIsSubmittingImport] = useState(false);

  const loadCatalogContext = useCallback(async () => {
    setIsLoadingCatalog(true);
    setPageError(null);

    try {
      const [manufacturersResponse, meterModelsResponse] = await Promise.all([
        authorizedFetch<MeterManufacturerListResponse>("/api/v1/manufacturers"),
        authorizedFetch<MeterModelListResponse>("/api/v1/models"),
      ]);
      setManufacturers(manufacturersResponse.items);
      setMeterModels(meterModelsResponse.items);
    } catch (error) {
      setManufacturers([]);
      setMeterModels([]);
      setPageError(
        error instanceof Error ? error.message : "Unable to load meter import catalog context.",
      );
    } finally {
      setIsLoadingCatalog(false);
    }
  }, [authorizedFetch]);

  useEffect(() => {
    void loadCatalogContext();
  }, [loadCatalogContext]);

  const readyRows = useMemo(
    () => previewRows.filter((row) => row.errors.length === 0),
    [previewRows],
  );
  const rowsWithIssues = useMemo(
    () => previewRows.filter((row) => row.errors.length > 0),
    [previewRows],
  );

  const handleFileSelection = useCallback(
    async (file: File | null) => {
      setSelectedFileName(file?.name ?? null);
      setPreviewRows([]);
      setRecognizedHeaders([]);
      setIgnoredHeaders([]);
      setParseError(null);
      setImportError(null);
      setImportSuccess(null);
      setImportResults([]);

      if (!file) {
        return;
      }

      try {
        const csvText = await file.text();
        const nextPreview = buildPreviewRows(csvText, manufacturers, meterModels);
        setPreviewRows(nextPreview.previewRows);
        setRecognizedHeaders(nextPreview.recognizedHeaders);
        setIgnoredHeaders(nextPreview.ignoredHeaders);
        setParseError(nextPreview.parseError);
      } catch (error) {
        setParseError(
          error instanceof Error ? error.message : "Unable to read the selected CSV file.",
        );
      }
    },
    [manufacturers, meterModels],
  );

  const handleImportSubmit = useCallback(async () => {
    setIsSubmittingImport(true);
    setImportError(null);
    setImportSuccess(null);
    setImportResults([]);

    const nextResults: ImportResult[] = [];

    try {
      for (const row of readyRows) {
        try {
          const response = await authorizedFetch<MeterCreateResponse>("/api/v1/meters", {
            method: "POST",
            body: JSON.stringify({
              serial_number: row.serialNumber,
              utility_meter_number: row.utilityMeterNumber,
              manufacturer_id: row.manufacturerId,
              meter_model_id: row.meterModelId,
              current_status: row.currentStatus,
            }),
          });
          nextResults.push({
            lineNumber: row.lineNumber,
            serialNumber: row.serialNumber,
            status: "imported",
            detail: "Meter record created.",
            createdMeterId: response.id,
          });
        } catch (error) {
          nextResults.push({
            lineNumber: row.lineNumber,
            serialNumber: row.serialNumber,
            status: "skipped",
            detail: error instanceof Error ? error.message : "Unable to create meter record.",
            createdMeterId: null,
          });
        }
      }

      setImportResults(nextResults);
      const importedCount = nextResults.filter((result) => result.status === "imported").length;
      const skippedCount = nextResults.filter((result) => result.status === "skipped").length;
      const invalidCount = rowsWithIssues.length;

      if (importedCount > 0) {
        const followUpCount = skippedCount + invalidCount;
        setImportSuccess(
          followUpCount > 0
            ? `${importedCount} meter record${importedCount === 1 ? "" : "s"} imported. ${followUpCount} row${followUpCount === 1 ? "" : "s"} require operator follow-up.`
            : `${importedCount} meter record${importedCount === 1 ? "" : "s"} imported successfully.`,
        );
      } else {
        setImportError("No meter records were imported. Review the row-level results below.");
      }
    } finally {
      setIsSubmittingImport(false);
    }
  }, [authorizedFetch, readyRows, rowsWithIssues.length]);

  return (
    <section className="panel">
      {pageError ? <p className="error-banner">{pageError}</p> : null}
      {parseError ? <p className="error-banner">{parseError}</p> : null}
      {importError ? <p className="error-banner">{importError}</p> : null}
      {importSuccess ? <p className="success-banner">{importSuccess}</p> : null}

      <div className="detail-stack">
        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h2>Meter import wizard</h2>
              <p className="muted">
                Bounded CSV onboarding flow for creating new meter records through the
                existing meter model and current write endpoint only.
              </p>
            </div>
            <span className="artifact-pill">CSV only</span>
          </div>

          <div className="artifact-row">
            <Link className="secondary-button" href="/meters">
              Return to meters
            </Link>
          </div>

          <div className="detail-stack">
            <label className="field">
              <span>Select meter CSV</span>
              <input
                accept=".csv,text/csv"
                aria-label="Meter import file"
                disabled={isLoadingCatalog}
                onChange={(event) => {
                  void handleFileSelection(event.target.files?.[0] ?? null);
                }}
                type="file"
              />
            </label>

            <p className="muted">
              Required CSV columns: `serial_number`, `manufacturer_code`, and
              `meter_model_code`. Optional columns: `utility_meter_number` and
              `current_status`.
            </p>
            <p className="muted">
              The wizard creates new meter records only. Duplicate or conflicting rows are
              skipped and reported during submission.
            </p>

            {selectedFileName ? (
              <div className="artifact-row">
                <span className="artifact-pill">{selectedFileName}</span>
              </div>
            ) : null}

            {isLoadingCatalog ? (
              <p className="muted">Loading meter import catalog context...</p>
            ) : null}
          </div>
        </section>

        <section className="subpanel">
          <div className="section-heading">
            <div>
              <h3>Review import</h3>
              <p className="muted">
                Confirm recognized fields, row counts, and duplicate or catalog issues
                before submitting the bounded import.
              </p>
            </div>
            <span className="artifact-pill">
              {previewRows.length} row{previewRows.length === 1 ? "" : "s"} loaded
            </span>
          </div>

          <div className="commands-selection-summary">
            <span className="artifact-pill">
              {readyRows.length} ready row{readyRows.length === 1 ? "" : "s"}
            </span>
            <span className="artifact-pill">
              {rowsWithIssues.length} row{rowsWithIssues.length === 1 ? "" : "s"} with issues
            </span>
            <span className="artifact-pill">
              {recognizedHeaders.length} recognized field
              {recognizedHeaders.length === 1 ? "" : "s"}
            </span>
          </div>

          {recognizedHeaders.length > 0 ? (
            <div className="artifact-row">
              {recognizedHeaders.map((header) => (
                <span key={header} className="artifact-pill">
                  {header}
                </span>
              ))}
            </div>
          ) : null}

          {ignoredHeaders.length > 0 ? (
            <p className="muted">
              Ignored CSV columns: {ignoredHeaders.join(", ")}.
            </p>
          ) : null}

          {previewRows.length === 0 && !parseError ? (
            <p className="muted">
              Select a CSV file to review mapped meter rows before import.
            </p>
          ) : null}

          {previewRows.length > 0 ? (
            <div className="command-list">
              {previewRows.map((row) => (
                <article key={`${row.lineNumber}-${row.serialNumber}`} className="command-list-item">
                  <div className="command-list-item-header">
                    <strong>{row.serialNumber || `Row ${row.lineNumber}`}</strong>
                    <div className="artifact-row">
                      <span
                        className={`status-pill ${row.errors.length === 0 ? "positive" : "danger"}`}
                      >
                        {row.errors.length === 0 ? "Ready to import" : "Needs review"}
                      </span>
                      <span className="artifact-pill">
                        {formatStatusLabel(row.currentStatus)}
                      </span>
                    </div>
                  </div>

                  <div className="command-list-item-meta">
                    <span>Line {row.lineNumber}</span>
                    <span>
                      Utility number {row.utilityMeterNumber ?? "not supplied"}
                    </span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>Manufacturer {row.manufacturerCode || "missing"}</span>
                    <span>Model {row.meterModelCode || "missing"}</span>
                  </div>
                  <div className="command-list-item-meta">
                    <span>
                      {row.manufacturerId && row.meterModelId
                        ? "Catalog mapping resolved"
                        : "Catalog mapping pending"}
                    </span>
                  </div>

                  {row.errors.length > 0 ? (
                    <p className="error-banner">{row.errors.join(" ")}</p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}

          <div className="artifact-row">
            <button
              className="primary-button"
              disabled={isSubmittingImport || readyRows.length === 0 || isLoadingCatalog}
              onClick={() => void handleImportSubmit()}
              type="button"
            >
              {isSubmittingImport ? "Submitting import..." : "Submit import"}
            </button>
          </div>
        </section>

        {importResults.length > 0 ? (
          <section className="subpanel">
            <div className="section-heading">
              <div>
                <h3>Import results</h3>
                <p className="muted">
                  Review imported rows and skipped records before continuing back into the
                  meters registry.
                </p>
              </div>
            </div>

            <div className="command-list">
              {importResults.map((result) => (
                <article key={`${result.lineNumber}-${result.serialNumber}`} className="command-list-item">
                  <div className="command-list-item-header">
                    <strong>{result.serialNumber}</strong>
                    <span
                      className={`status-pill ${
                        result.status === "imported" ? "positive" : "warning"
                      }`}
                    >
                      {result.status === "imported" ? "Imported" : "Skipped"}
                    </span>
                  </div>

                  <div className="command-list-item-meta">
                    <span>Line {result.lineNumber}</span>
                    <span>{result.detail}</span>
                  </div>

                  {result.createdMeterId ? (
                    <div className="artifact-row">
                      <Link className="secondary-button" href={`/meters/${result.createdMeterId}`}>
                        Open imported meter
                      </Link>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}

function formatStatusLabel(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
