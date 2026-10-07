import { http, HttpResponse } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import BillingInvoicePage from "./invoice-page";
import { billingServer } from "../../test-setup";

const TENANT = "00000000-0000-0000-0000-000000000006";
const INVOICE = "6a1c9e8b-0000-4000-8000-000000000001";
const BASE = "http://localhost:3000/billing-api/api";
const line = (line_no: number, line_type: string, description: string, amount: string) => ({
  line_no,
  line_type,
  description,
  amount,
  tax_amount: "0",
  credit_applied: "0",
  total: amount,
});
const PREVIEW = [
  line(1, "plan", "STARTER", "49.00"),
  line(2, "usage", "usage overage", "5.56"),
  line(3, "tax", "regional tax", "2.2506"),
  line(4, "tax", "local tax", "2.2506"),
  line(5, "credit", "credit notes", "0"),
];

function renderPage(tenantId = TENANT) {
  return render(
    <MemoryRouter initialEntries={[`/billing/invoice/${tenantId}`]}>
      <Routes>
        <Route path="/billing/invoice/:tenantId" element={<BillingInvoicePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function usePreviewHandler() {
  billingServer.use(
    http.get(`${BASE}/tenants/${TENANT}/invoice-preview`, ({ request }) => {
      const url = new URL(request.url);
      expect(url.searchParams.get("period_start")).toBe("2026-02-01");
      expect(url.searchParams.get("period_end")).toBe("2026-02-28");
      return HttpResponse.json(PREVIEW);
    }),
  );
}

describe("Billing invoice", () => {
  it("renders the five preview lines", async () => {
    usePreviewHandler();
    renderPage();
    const preview = await screen.findByLabelText("Invoice preview");
    expect(preview).toHaveTextContent("STARTER");
    expect(preview).toHaveTextContent("regional tax");
    expect(preview).toHaveTextContent("credit notes");
    expect(screen.getAllByRole("row")).toHaveLength(6);
  });

  it("issues the invoice and shows the stored lines", async () => {
    usePreviewHandler();
    billingServer.use(
      http.post(`${BASE}/tenants/${TENANT}/invoices`, async ({ request }) => {
        expect(await request.json()).toEqual({
          period_start: "2026-02-01",
          period_end: "2026-02-28",
        });
        const state = { status: "issued", subtotal: "54.56", tax: "4.50", total: "59.06" };
        return HttpResponse.json({
          ...state,
          invoice_id: INVOICE,
          period_id: "p",
          issued_at: "2026-02-28T00:00:00+00:00",
          invoice_state: [state],
          credit_notes: [],
        });
      }),
      http.get(`${BASE}/invoices/${INVOICE}/lines`, () =>
        HttpResponse.json([
          { line_no: 1, line_type: "plan", description: "STARTER", amount: "49.00" },
          { line_no: 3, line_type: "tax", description: "regional tax", amount: "2.25" },
        ]),
      ),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Issue invoice" }));
    const issued = await screen.findByLabelText("Issued invoice");
    expect(issued).toHaveTextContent("total 59.06");
    expect(await screen.findByText("regional tax: 2.25")).toBeInTheDocument();
  });

  it("shows an error when the invoice cannot be issued", async () => {
    usePreviewHandler();
    billingServer.use(
      http.post(`${BASE}/tenants/${TENANT}/invoices`, () =>
        HttpResponse.json({ detail: "negative total" }, { status: 409 }),
      ),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Issue invoice" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The invoice could not be issued.");
  });

  it("shows an error when the tenant has no subscription", async () => {
    billingServer.use(
      http.get(`${BASE}/tenants/${TENANT}/invoice-preview`, () =>
        HttpResponse.json({ detail: "no subscription" }, { status: 404 }),
      ),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The invoice preview could not be loaded.",
    );
  });

  it("rejects an invalid tenant id without calling the service", async () => {
    renderPage("not-a-tenant");
    expect(await screen.findByRole("alert")).toHaveTextContent("A valid tenant id is required.");
  });
});
