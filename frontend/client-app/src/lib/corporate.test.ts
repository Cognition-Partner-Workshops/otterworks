import { describe, it, expect } from "vitest";
import {
  COMPANY,
  FOUNDING_STORY,
  LEADERSHIP,
  DEPARTMENTS,
  PRODUCTS,
  PRESS_RELEASES,
  CAREERS,
} from "./corporate";

// AC-03 / BDD-07: the corporate identity content is complete and clearly fictional.
describe("corporate identity content", () => {
  it("identifies the company and its Hollin Valley utility tagline", () => {
    expect(COMPANY.name).toBe("Hollinmere Power & Light");
    expect(COMPANY.tagline).toBe("Power, grid and field crews for the Hollin Valley");
  });

  it("declares the content fictional", () => {
    expect(COMPANY.disclaimer).toMatch(/fictional/i);
  });

  it("provides every corporate identity section", () => {
    expect(FOUNDING_STORY.length).toBeGreaterThan(0);
    expect(LEADERSHIP.length).toBeGreaterThanOrEqual(3);
    expect(DEPARTMENTS.length).toBeGreaterThanOrEqual(3);
    expect(PRODUCTS.length).toBeGreaterThanOrEqual(3);
    expect(PRESS_RELEASES.length).toBeGreaterThanOrEqual(3);
    expect(CAREERS.length).toBeGreaterThanOrEqual(3);
  });

  it("gives each leader a name, title, and bio", () => {
    for (const leader of LEADERSHIP) {
      expect(leader.name).toBeTruthy();
      expect(leader.title).toBeTruthy();
      expect(leader.bio).toBeTruthy();
    }
  });
});
