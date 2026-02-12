import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load. Streamlit apps can take a moment.
  // We check for a known element. The memory mentions "Saved Cases" tab.
  // "Dashboard" is also a tab.

  // Using .first() as per memory to avoid strict mode violations if multiple exist
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible({ timeout: 30000 });

  // Optional: Check for "Saved Cases" as well
  await expect(page.getByRole('tab', { name: 'Saved Cases' }).first()).toBeVisible();
});
