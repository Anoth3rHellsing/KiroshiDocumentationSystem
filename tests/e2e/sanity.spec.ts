
import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  // The app is served at the base URL configured in playwright.config.ts
  await page.goto('/');

  // Verify the title contains "Kiroshi"
  await expect(page).toHaveTitle(/Kiroshi/);
});
