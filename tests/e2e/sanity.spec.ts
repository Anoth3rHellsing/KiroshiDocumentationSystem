import { test, expect } from '@playwright/test';

test('sanity check: app loads', async ({ page }) => {
  // Increase timeout for cold starts
  test.setTimeout(60000);

  await page.goto('/');

  // Wait for the main app container to ensure Streamlit has mounted
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 45000 });

  // Verify key tabs exist to confirm UI structure
  // Using exact: true prevents matching "Dashboard" text that might appear in logs/content
  await expect(page.getByRole('tab', { name: 'Dashboard', exact: true })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Sprint', exact: true })).toBeVisible();
});
