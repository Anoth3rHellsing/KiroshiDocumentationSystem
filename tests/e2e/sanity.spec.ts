import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toBeVisible();
});
