export function money(cents: number): string {
  return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

const ALPHA = ["XXS", "XS", "S", "M", "L", "XL", "XXL"];
const BABY = ["0-3M", "3-6M", "6-12M", "12-18M", "18-24M"];

export function sizeRank(size: string): number {
  const a = ALPHA.indexOf(size);
  if (a >= 0) return a;
  const b = BABY.indexOf(size);
  if (b >= 0) return 100 + b;
  const n = parseInt(size, 10);
  return Number.isNaN(n) ? 1000 : 200 + n;
}

export function sortSizes<T extends { value: string }>(facets: T[]): T[] {
  return [...facets].sort((x, y) => sizeRank(x.value) - sizeRank(y.value));
}
