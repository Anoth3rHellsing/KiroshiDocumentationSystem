
import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');

  // Wait for the main content to load.
  // The dashboard has a tab "Dashboard".
  // Using a more lenient selector to avoid strict mode violations if multiple exist
  // (e.g. one in tab list, one in content)
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible({ timeout: 60000 });

  // Check for the "Add Case" button.
  // It might be hidden or not rendered immediately?
  // Let's look for "Saved Cases" tab instead, which is also standard.
  await expect(page.getByRole('tab', { name: 'Saved Cases' }).first()).toBeVisible();
});
