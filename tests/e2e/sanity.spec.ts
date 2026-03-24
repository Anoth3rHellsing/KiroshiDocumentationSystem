import { test, expect } from '@playwright/test';

test('App should load', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('tab', { name: 'Saved Cases' }).first()).toBeVisible();
});