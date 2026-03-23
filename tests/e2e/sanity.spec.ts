import { test, expect } from '@playwright/test';

test('Application loads and shows dashboard', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible();
});
