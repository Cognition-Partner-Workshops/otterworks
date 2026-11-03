import { describe, expect, it } from "vitest";
import { money, sizeRank, sortSizes, titleCase } from "./format";

describe("money", () => {
  it("formats cents as US dollars", () => {
    expect(money(0)).toBe("$0.00");
    expect(money(10)).toBe("$0.10");
    expect(money(29)).toBe("$0.29");
    expect(money(123456)).toBe("$1,234.56");
  });
  it("keeps the sign on refunds and credits", () => {
    expect(money(-500)).toBe("-$5.00");
  });
});

describe("titleCase", () => {
  it("capitalizes each word", () => expect(titleCase("new arrivals")).toBe("New Arrivals"));
});

describe("size ordering", () => {
  it("orders alpha, then baby, then numeric sizes, unknown last", () => {
    const sizes = ["XL", "32", "S", "6-12M", "0-3M", "One Size", "28", "XXS"];
    expect([...sizes].sort((a, b) => sizeRank(a) - sizeRank(b))).toEqual(["XXS", "S", "XL", "0-3M", "6-12M", "28", "32", "One Size"]);
  });
  it("sortSizes does not mutate its input", () => {
    const facets = [{ value: "L" }, { value: "XS" }];
    expect(sortSizes(facets).map((f) => f.value)).toEqual(["XS", "L"]);
    expect(facets[0].value).toBe("L");
  });
});
