import { test, expect } from '@playwright/test';

test('App loads successfully and shows Dashboard tab', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('tab', { name: 'Dashboard' }).first()).toBeVisible();
});
