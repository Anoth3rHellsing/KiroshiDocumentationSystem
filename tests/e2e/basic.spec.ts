import { test, expect } from '@playwright/test';

test('basic load', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/.*Kiroshi.*/i); // Just an example, replace or make it general
});
