import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FnolForm } from "./fnol-page";

const change = (label: RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

function fillValid() {
  change(/policy number/i, "POL-AUTO-48100");
  change(/given name/i, "Imogen");
  change(/surname/i, "Castellanos");
  change(/tax id/i, "100-40-7000");
  change(/loss date/i, "2026-09-02");
  change(/cause of loss/i, "GLAS");
  change(/description/i, "Windscreen cracked by road debris");
  change(/estimated loss/i, "412");
  fireEvent.click(screen.getByLabelText("No"));
  change(/city/i, "Bristol");
  change(/state/i, "RI");
  change(/postal code/i, "02809");
}

describe("FnolForm", () => {
  it("offers exactly the eight hub cause codes", () => {
    render(<FnolForm submit={vi.fn()} />);
    const options = within(screen.getByLabelText(/cause of loss/i))
      .getAllByRole("option")
      .map((o) => (o as HTMLOptionElement).value)
      .filter(Boolean);
    expect(options).toEqual(["COLL", "COMP", "GLAS", "THFT", "FIRE", "WATR", "WIND", "LIAB"]);
  });

  it("shows the photos placeholder with capture disabled", () => {
    render(<FnolForm submit={vi.fn()} />);
    const box = screen.getByTestId("photos-placeholder");
    expect(within(box).getByRole("button", { name: /add photos/i })).toBeDisabled();
  });

  it("blocks submit until required fields and the injury answer are given", async () => {
    const submit = vi.fn();
    render(<FnolForm submit={submit} />);
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    expect(await screen.findByText("Policy number is required")).toBeInTheDocument();
    expect(screen.getByText("Choose a cause of loss")).toBeInTheDocument();
    expect(screen.getByText("Say whether anyone was injured")).toBeInTheDocument();
    expect(screen.getByText("Description is required")).toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
  });

  it("rejects a loss date in the future", async () => {
    render(<FnolForm submit={vi.fn()} />);
    fillValid();
    change(/loss date/i, "2999-01-01");
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    expect(await screen.findByText("Loss date cannot be in the future")).toBeInTheDocument();
  });

  it("fills line of business from the policy prefix", () => {
    render(<FnolForm submit={vi.fn()} />);
    change(/policy number/i, "POL-HOME-48142");
    expect(screen.getByLabelText(/line of business/i)).toHaveValue("HOME");
  });

  it("clears the line-of-business error once the policy prefix fills it", async () => {
    render(<FnolForm submit={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    expect(await screen.findByText("Choose a line of business")).toBeInTheDocument();
    change(/policy number/i, "POL-AUTO-48100");
    await waitFor(() => expect(screen.queryByText("Choose a line of business")).not.toBeInTheDocument());
  });

  it("masks the tax id on the device and posts the ACORD request", async () => {
    const submit = vi.fn().mockResolvedValue({});
    render(<FnolForm submit={submit} />);
    fillValid();
    expect(screen.getByTestId("tax-id-preview")).toHaveTextContent("XXX-XX-7000");
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    const xml: string = submit.mock.calls[0][0];
    expect(xml).not.toContain("100-40-7000");
    expect(xml).toContain("<TaxId>XXX-XX-7000</TaxId>");
    expect(xml).toMatch(/^<ns0:ClaimsSvcRq xmlns:ns0="http:\/\/schemas\.thistlecombe\.example\/acord\/claims\/fnol">/);
    expect(xml).toContain("<LOBCd>AUTO</LOBCd>");
    expect(xml).toContain("<LossCauseCd>GLAS</LossCauseCd>");
    expect(xml).toContain("<InjuryInd>false</InjuryInd>");
    const receipt = await screen.findByTestId("fnol-receipt");
    expect(receipt).toHaveTextContent("XXX-XX-7000");
    expect(receipt).toHaveTextContent(/CLM-\d{4}-M[0-9A-F]{8}/);
  });

  it("surfaces a hub rejection and keeps the form", async () => {
    const submit = vi.fn().mockRejectedValue({ response: { data: { error: "schema_invalid" } } });
    render(<FnolForm submit={submit} />);
    fillValid();
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    expect(await screen.findByText("Claims hub rejected the notice: schema_invalid")).toBeInTheDocument();
    expect(screen.getByLabelText(/policy number/i)).toHaveValue("POL-AUTO-48100");
  });

  it("retries with the same request id and claim number", async () => {
    const submit = vi.fn().mockRejectedValueOnce(new Error("timeout")).mockResolvedValue({});
    render(<FnolForm submit={submit} />);
    fillValid();
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    expect(await screen.findByText("Could not reach the claims hub. Try again.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
    const ids = submit.mock.calls.map((call) => {
      const xml = String(call[0]);
      return [/<RqUID>([^<]+)</.exec(xml)?.[1], /<ClaimNumber>([^<]+)</.exec(xml)?.[1]];
    });
    expect(ids[1]).toEqual(ids[0]);
  });

  it("rejects a line of business that contradicts the policy number", async () => {
    const submit = vi.fn();
    render(<FnolForm submit={submit} />);
    fillValid();
    fireEvent.change(screen.getByLabelText(/line of business/i), { target: { value: "HOME" } });
    fireEvent.click(screen.getByRole("button", { name: /submit first notice/i }));
    expect(await screen.findByText("Line of business does not match the policy number")).toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
  });
});
