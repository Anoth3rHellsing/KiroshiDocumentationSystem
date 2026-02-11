
import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');

  // Wait for the main content to load.
  // The dashboard has a tab "Dashboard".
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });

  // Check for the "Add Case" button (always present in the tab list)
  await expect(page.getByRole('button', { name: 'Add Case' })).toBeVisible();
});
