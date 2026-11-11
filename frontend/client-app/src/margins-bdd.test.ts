import { describe, expect, it, vi } from "vitest";

const step = vi.hoisted(() => ({ run: undefined as ((this: unknown) => Promise<void>) | undefined }));
vi.mock("@cucumber/cucumber", () => ({
  Given: (_name: string, callback: typeof step.run) => { step.run = callback; },
  Then: vi.fn(),
}));
vi.mock("@playwright/test", () => ({ expect: () => ({ toHaveURL: vi.fn() }) }));

import "../bdd/steps/margins.steps";

function page() {
  const fields: Record<string, string> = {};
  return {
    fields,
    goto: vi.fn(),
    getByLabel: (name: string) => ({ fill: async (value: string) => { fields[name] = value; } }),
    getByRole: () => ({ click: vi.fn() }),
  };
}

describe("margins BDD signup credentials", () => {
  it("uses fresh cryptographic account identifiers and matching random passwords", async () => {
    const first = page();
    const second = page();
    await step.run!.call({ page: first });
    await step.run!.call({ page: second });
    expect(first.fields.Email).toMatch(/^bdd-margins-[0-9a-f-]{36}@otterworks\.test$/);
    expect(first.fields.Password).toMatch(/^Bdd-[0-9a-f]{48}!23$/);
    expect(first.fields.Password).toBe(first.fields["Confirm password"]);
    expect(first.fields.Email).not.toBe(second.fields.Email);
    expect(first.fields.Password).not.toBe(second.fields.Password);
  });

  it("propagates navigation failures", async () => {
    const broken = page();
    broken.goto.mockRejectedValue(new Error("navigation failed"));
    await expect(step.run!.call({ page: broken })).rejects.toThrow("navigation failed");
  });
});
