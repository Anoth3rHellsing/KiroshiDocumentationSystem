
import { test, expect } from '@playwright/test';

test('Sanity check: Application loads', async ({ page }) => {
  // Assuming the base URL is set in config
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
});
