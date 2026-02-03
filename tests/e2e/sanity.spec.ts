import { test, expect } from '@playwright/test';

test('app loads and title is correct', async ({ page }) => {
  await page.goto('/');
  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Kiroshi/);
});
