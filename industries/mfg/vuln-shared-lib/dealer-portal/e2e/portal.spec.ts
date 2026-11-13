import { expect, Page, test } from '@playwright/test';

async function signIn(page: Page): Promise<void> {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill('dealer-ops@dealer.example');
  await page.getByLabel('Password').fill('vsl-synthetic-portal-pass');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/inventory$/);
}

test('redirects to sign-in when there is no session', async ({ page }) => {
  await page.goto('/claims');
  await expect(page).toHaveURL(/\/sign-in\?returnUrl=%2Fclaims$/);
});

test('rejects a wrong password', async ({ page }) => {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill('dealer-ops@dealer.example');
  await page.getByLabel('Password').fill('wrong');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('Sign-in failed');
});

test('signs in and browses inventory', async ({ page }) => {
  await signIn(page);
  await expect(page.getByTestId('dealer-id')).toHaveText('D-1001');
  await expect(page.getByTestId('vehicle-row')).toHaveCount(3);

  await page.getByPlaceholder('Search by VIN or model').fill('ranger');
  await page.getByRole('button', { name: 'Search' }).click();
  await expect(page).toHaveURL(/q=ranger/);
  await expect(page.getByTestId('vehicle-row')).toHaveCount(2);
  await expect(page.getByTestId('search-summary')).toHaveText('2 vehicles match ranger');

  await page.getByRole('link', { name: '1VSLA0000AA000003' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('2026 Ranger Sport');
  await expect(page.getByTestId('vehicle-vin')).toHaveText('1VSLA0000AA000003');
});

test('submits a warranty claim from a vehicle', async ({ page }) => {
  await signIn(page);
  await page.goto('/inventory/1VSLA0000AA000001');
  await page.getByRole('link', { name: 'File a warranty claim' }).click();
  await expect(page.getByLabel('VIN')).toHaveValue('1VSLA0000AA000001');
  await page.getByLabel('What went wrong?').fill('Passenger door seal leaks in heavy rain');
  await page.getByRole('button', { name: 'Submit claim' }).click();

  await expect(page).toHaveURL(/\/claims$/);
  const first = page.getByTestId('claim-row').first();
  await expect(first).toContainText('1VSLA0000AA000001');
  await expect(first).toContainText('Passenger door seal leaks in heavy rain');
});

test('shows dealer notices from the bulletin feed', async ({ page }) => {
  await signIn(page);
  await page.getByRole('link', { name: 'Notices' }).click();
  const notices = page.getByTestId('notice');
  await expect(notices).toHaveCount(2);
  await expect(notices.first().getByRole('heading')).toHaveText('Brake hose inspection');
  await expect(notices.first().locator('time')).toHaveText('1 Feb 2026');
});

test('signs out', async ({ page }) => {
  await signIn(page);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
  await page.goto('/inventory');
  await expect(page).toHaveURL(/\/sign-in/);
});
