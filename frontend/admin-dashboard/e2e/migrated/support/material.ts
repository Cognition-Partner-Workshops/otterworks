import type { Locator, Page } from "@playwright/test";

export function matSelect(page: Page, label: string): { trigger: Locator; options: Locator } {
  return {
    trigger: page.getByRole("combobox", { name: label }),
    options: page.getByRole("listbox", { name: label }).getByRole("option"),
  };
}

export async function typeIntoFilter(input: Locator, value: string): Promise<void> {
  await input.clear();
  await input.pressSequentially(value);
}
