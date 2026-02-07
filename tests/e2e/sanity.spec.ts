import { test, expect } from '@playwright/test';

test('sanity', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('[data-testid="stAppViewContainer"]');

  // Check for the Dashboard tab specifically to avoid ambiguity with the header
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Check for 'Tracked Cases' which should be unique on the dashboard
  await expect(page.getByText('Tracked Cases', { exact: true })).toBeVisible();
});
