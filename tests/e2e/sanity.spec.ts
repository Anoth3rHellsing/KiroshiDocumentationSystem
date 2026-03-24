import { test, expect } from '@playwright/test';

test('app loads and shows Dashboard', async ({ page }) => {
  await page.goto('http://localhost:8501');
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' }).first();
  await expect(dashboardTab).toBeVisible({ timeout: 15000 });
});
