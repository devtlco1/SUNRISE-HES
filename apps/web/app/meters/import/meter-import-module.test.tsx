import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationalShell } from "../../operational-shell";
import { MeterImportModule } from "./meter-import-module";

function includesText(text: string) {
  return (_content: string, element: Element | null) => element?.textContent?.includes(text) ?? false;
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createMockApi({
  manufacturers = [
    {
      id: "manufacturer-1",
      code: "generic",
      name: "Generic Meters",
    },
  ],
  meterModels = [
    {
      id: "model-1",
      manufacturer_id: "manufacturer-1",
      manufacturer_code: "generic",
      model_code: "gm-1",
      display_name: "GM-1",
    },
  ],
  createFailuresBySerial = {} as Record<string, { detail: string; status?: number }>,
}: {
  manufacturers?: Array<Record<string, unknown>>;
  meterModels?: Array<Record<string, unknown>>;
  createFailuresBySerial?: Record<string, { detail: string; status?: number }>;
} = {}) {
  let createdCount = 0;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();

    if (url.endsWith("/api/v1/auth/me")) {
      return jsonResponse({
        id: "user-1",
        username: "ops.user",
        email: "ops@example.com",
        full_name: "Ops User",
        status: "active",
        is_superuser: true,
      });
    }

    if (url.endsWith("/api/v1/manufacturers")) {
      return jsonResponse({
        total: manufacturers.length,
        items: manufacturers,
      });
    }

    if (url.endsWith("/api/v1/models")) {
      return jsonResponse({
        total: meterModels.length,
        items: meterModels,
      });
    }

    if (url.endsWith("/api/v1/meters") && init?.method === "POST") {
      const payload = JSON.parse(String(init.body ?? "{}")) as {
        serial_number: string;
      };
      const configuredFailure = createFailuresBySerial[payload.serial_number];
      if (configuredFailure) {
        return jsonResponse(
          { detail: configuredFailure.detail },
          configuredFailure.status ?? 409,
        );
      }

      createdCount += 1;
      return jsonResponse(
        {
          id: `created-meter-${createdCount}`,
          serial_number: payload.serial_number,
        },
        201,
      );
    }

    throw new Error(`Unhandled request: ${url}`);
  });

  return { fetchMock };
}

function renderMeterImportModuleInShell() {
  render(
    <OperationalShell
      eyebrow="Operational Pages"
      title="Meter Import Wizard MVP"
      description="Bounded meter import wizard"
    >
      {({ authorizedFetch }) => <MeterImportModule authorizedFetch={authorizedFetch} />}
    </OperationalShell>,
  );
}

describe("MeterImportModule", () => {
  beforeEach(() => {
    window.localStorage.setItem("sunrise.web.apiBaseUrl", "http://localhost:8000");
    window.localStorage.setItem("sunrise.web.accessToken", "token-1");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the meter import wizard inside the shared shell", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);

    renderMeterImportModuleInShell();

    expect(await screen.findByRole("heading", { name: "Meter import wizard" })).toBeInTheDocument();
    expect(
      screen.getByText(/Required CSV columns: `serial_number`, `manufacturer_code`, and `meter_model_code`./),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return to meters" })).toHaveAttribute(
      "href",
      "/meters",
    );
  });

  it("supports CSV upload and renders a bounded review preview", async () => {
    const { fetchMock } = createMockApi();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterImportModuleInShell();

    const fileInput = await screen.findByLabelText("Meter import file");
    await waitFor(() => {
      expect(fileInput).not.toBeDisabled();
    });
    const csvFile = new File(
      [
        [
          "serial_number,manufacturer_code,meter_model_code,utility_meter_number,current_status",
          "SN-2001,generic,gm-1,UMN-2001,registered",
          "SN-2002,generic,gm-1,,commissioned",
        ].join("\n"),
      ],
      "meter-import.csv",
      { type: "text/csv" },
    );

    await user.upload(fileInput, csvFile);

    await waitFor(() => {
      expect(screen.getAllByText(includesText("meter-import.csv")).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(includesText("2 rows loaded")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(includesText("2 ready rows")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(includesText("0 rows with issues")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(includesText("5 recognized fields")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Catalog mapping resolved").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Submit import" })).toBeEnabled();
  });

  it("reports duplicate rows and conflicting create responses during import submission", async () => {
    const { fetchMock } = createMockApi({
      createFailuresBySerial: {
        "SN-2003": {
          detail: "Serial number already exists.",
        },
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterImportModuleInShell();

    const fileInput = await screen.findByLabelText("Meter import file");
    await waitFor(() => {
      expect(fileInput).not.toBeDisabled();
    });
    const csvFile = new File(
      [
        [
          "serial_number,manufacturer_code,meter_model_code,utility_meter_number,current_status",
          "SN-2001,generic,gm-1,UMN-2001,registered",
          "SN-2002,generic,gm-1,UMN-2002,registered",
          "SN-2002,generic,gm-1,UMN-2003,registered",
          "SN-2003,generic,gm-1,UMN-2004,registered",
        ].join("\n"),
      ],
      "meter-import-conflicts.csv",
      { type: "text/csv" },
    );

    await user.upload(fileInput, csvFile);

    await waitFor(() => {
      expect(screen.getAllByText(includesText("4 rows loaded")).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(includesText("2 rows with issues")).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Serial number is duplicated within this CSV file.").length,
    ).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Submit import" }));

    expect(
      await screen.findByText("1 meter record imported. 3 rows require operator follow-up."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Import results" })).toBeInTheDocument();
    expect(screen.getByText("Meter record created.")).toBeInTheDocument();
    expect(screen.getByText("Serial number already exists.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open imported meter" })).toHaveAttribute(
      "href",
      "/meters/created-meter-1",
    );
  });

  it("shows a bounded import error when no valid rows can be imported", async () => {
    const { fetchMock } = createMockApi({
      createFailuresBySerial: {
        "SN-2004": {
          detail: "Serial number already exists.",
        },
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderMeterImportModuleInShell();

    const fileInput = await screen.findByLabelText("Meter import file");
    await waitFor(() => {
      expect(fileInput).not.toBeDisabled();
    });
    const csvFile = new File(
      [
        [
          "serial_number,manufacturer_code,meter_model_code",
          "SN-2004,generic,gm-1",
        ].join("\n"),
      ],
      "meter-import-error.csv",
      { type: "text/csv" },
    );

    await user.upload(fileInput, csvFile);
    await user.click(screen.getByRole("button", { name: "Submit import" }));

    await waitFor(() => {
      expect(
        screen.getAllByText(
          includesText("No meter records were imported. Review the row-level results below."),
        ).length,
      ).toBeGreaterThan(0);
    });
    const resultsPanel = screen.getByRole("heading", { name: "Import results" }).closest("section");
    expect(resultsPanel).not.toBeNull();
    await waitFor(() => {
      expect(within(resultsPanel as HTMLElement).getByText("Skipped")).toBeInTheDocument();
      expect(within(resultsPanel as HTMLElement).getByText("Serial number already exists.")).toBeInTheDocument();
    });
  });
});
