import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FnolIntake } from "./fnol-intake";
import { ClaimStatusPage } from "./claim-status";
import { PaymentConfirmation } from "./payment-confirmation";

function serve(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const body = routes[key];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: `no ${key}` } };
  }));
}

function at(path: string, pattern: string, element: JSX.Element) {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path={pattern} element={element} /></Routes></MemoryRouter>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("claims screens", () => {
  it("submits a corpus FNOL and shows the claim number and triage outcome the API returned", async () => {
    serve({
      "GET /api/claims-screens/fnol": { fnols: ["CLM-2026-100400", "CLM-2026-100405"] },
      "POST /api/claims-screens/fnol/CLM-2026-100405": { claimNumber: "CLM-2026-100405", outcome: "FRAUD_REVIEW", reasons: ["Reported more than 30 days after loss"], fnolStatus: "COMPLETED", evidence: ["x"] },
    });
    at("/", "/", <FnolIntake />);
    const select = await screen.findByLabelText("Corpus FNOL");
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2));
    fireEvent.change(select, { target: { value: "CLM-2026-100405" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit FNOL" }));
    expect(await screen.findByTestId("claim-number")).toHaveTextContent("CLM-2026-100405");
    expect(screen.getByTestId("outcome")).toHaveTextContent("FRAUD_REVIEW");
    expect(screen.getByText("Reported more than 30 days after loss")).toBeInTheDocument();
  });

  it("says why there is no adjuster instead of inventing one", async () => {
    serve({
      "GET /api/claims-screens/claims/CLM-2026-100403": {
        claimNumber: "CLM-2026-100403", outcome: "DECLINE_NOT_IN_FORCE", reasons: ["Policy not in force at loss date"], fnolStatus: "TERMINATED", evidence: ["x"],
        claimant: "A", lossCause: "COLL", policy: { number: "POL-AUTO-48121", status: "Lapsed", lineOfBusiness: "AUTO", effectiveDate: "2025-01-01", inForceAtLoss: "false" },
        adjuster: null, missing: { adjuster: "no assignment notice for this claim in the SMTP sink" },
      },
    });
    at("/claims/CLM-2026-100403", "/claims/:claim", <ClaimStatusPage />);
    expect(await screen.findByText("no assignment notice for this claim in the SMTP sink")).toBeInTheDocument();
    expect(screen.getAllByTestId("outcome")[0]).toHaveTextContent("DECLINE_NOT_IN_FORCE");
  });

  it("shows ledger net and file net as written, and the difference between them", async () => {
    serve({
      "GET /api/claims-screens/payments/PI-2026-880107": {
        instructionId: "PI-2026-880107", claimNumber: "CLM-2026-100405", policyNumber: "POL-AUTO-48177", vendorCode: "PAYV02", valueDate: "2026-10-08", currency: "USD",
        payee: { name: "Imogen Castellanos", type: "CL", account: "****1511" },
        lines: [{ lineNo: 1, lineType: "IND", amount: "0.015", glAccount: "61010100", memo: "m" }],
        ledger: { vendorReference: "CLM2026100405880107-76", indemnityAmount: "1234.58", expenseAmount: "0.50", salvageCredit: "0.00", netAmount: "1235.08", lineCount: "3" },
        remittance: { fileName: "f.txt", lines: [{ seq: 1, lineType: "IND", amountCents: 2, direction: "D", glAccount: "61010100" }], trailer: { count: 3, netCents: 123509 }, trailerMatchesLines: true },
        fileStatus: { state: "DELIVERED", detail: "d" }, differences: ["Ledger net 1235.08 vs remittance file net 1235.09"], evidence: ["x"],
      },
    });
    at("/payments/PI-2026-880107", "/payments/:id", <PaymentConfirmation />);
    expect(await screen.findByTestId("ledger-net")).toHaveTextContent("1235.08");
    expect(screen.getByTestId("file-net")).toHaveTextContent("1235.09");
    expect(screen.getByTestId("vendor-reference")).toHaveTextContent("CLM2026100405880107-76");
    expect(screen.getByTestId("difference")).toHaveTextContent("1235.09");
    expect(screen.getByText("0.02 D")).toBeInTheDocument();
  });
});
