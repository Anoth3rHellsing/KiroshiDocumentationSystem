import { test, expect } from '@playwright/test';

test('sanity check: app loads', async ({ page }) => {
  // The baseURL is configured in playwright.config.ts (usually localhost:8501)
  await page.goto('/');

  // Streamlit apps can take a moment to load
  // We check for a known element from the Dashboard or Tab list
  // "Dashboard", "Sprint", "Saved Cases" are the main tabs.

  // Wait for the tab list to appear
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole('tab', { name: 'Saved Cases' }).first()).toBeVisible();
});
