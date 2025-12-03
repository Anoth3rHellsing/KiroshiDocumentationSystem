import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

type ThemeConfig = {
  name: string;
  query: Record<string, string>;
};

type Breakpoint = {
  name: string;
  viewport: { width: number; height: number };
};

const THEMES: ThemeConfig[] = [
  {
    name: 'base',
    query: {
      enable_holiday_theme: 'false',
      theme_preview: 'auto',
    },
  },
  {
    name: 'holiday',
    query: {
      enable_holiday_theme: 'true',
      theme_preview: 'christmas',
    },
  },
  {
    name: 'dark',
    query: {
      dark_mode: 'true',
      enable_holiday_theme: 'false',
    },
  },
];

const BREAKPOINTS: Breakpoint[] = [
  {
    name: 'desktop',
    viewport: { width: 1440, height: 900 },
  },
  {
    name: 'tablet',
    viewport: { width: 1024, height: 1366 },
  },
];

function buildUrl(baseURL: string, params: Record<string, string>): string {
  const url = new URL('/', baseURL);
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      search.set(key, value);
    }
  }
  url.search = search.toString();
  return url.toString();
}

async function loadDashboard(
  baseURL: string | undefined,
  page: Page,
  params: Record<string, string>,
) {
  if (!baseURL) {
    throw new Error('A baseURL must be configured for Playwright tests.');
  }
  const targetUrl = buildUrl(baseURL, params);
  await page.goto(targetUrl, { waitUntil: 'networkidle' });
  const appRoot = page.locator('div[data-testid="stAppViewContainer"]');
  await expect(appRoot).toBeVisible();
  // Give Streamlit time to finish lazy layout adjustments before snapshotting.
  await page.waitForTimeout(1500);
}

test.describe('Dashboard visual themes', () => {
  for (const theme of THEMES) {
    test.describe(theme.name, () => {
      for (const breakpoint of BREAKPOINTS) {
        test(`${theme.name} theme – ${breakpoint.name}`, async ({ page, baseURL }) => {
          await page.setViewportSize(breakpoint.viewport);
          await loadDashboard(baseURL, page, theme.query);
          await expect(page).toHaveScreenshot(`${theme.name}-${breakpoint.name}.png`, {
            fullPage: true,
            animations: 'disabled',
            caret: 'hide',
            maxDiffPixelRatio: 0.01,
          });
        });
      }
    });
  }
});
