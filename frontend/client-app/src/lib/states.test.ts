import { describe, expect, it } from "vitest";
import { STATES } from "./states";

describe("STATES", () => {
  it("lists the 50 states plus DC once each", () => {
    expect(STATES).toHaveLength(51);
    expect(new Set(STATES).size).toBe(51);
    expect(STATES).toEqual(expect.arrayContaining(["CA", "CO", "DC", "OR"]));
  });
});
