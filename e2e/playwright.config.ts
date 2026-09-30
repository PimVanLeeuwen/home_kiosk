import { defineConfig, devices } from '@playwright/test'

const PORT = 18083
const IMAGE = 'home-hub-e2e'

/**
 * Runs against the real dashboard image (Caddy serving the hub and the kiosk),
 * built from the working tree. There is no collector: tests that need API data
 * stub /api themselves, everything else sees the 502 a cold NAS would give.
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    colorScheme: 'dark',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    // Chromium rather than WebKit, so one browser download covers both projects.
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  globalTeardown: './teardown.ts',
  webServer: {
    command: [
      `docker rm -f ${IMAGE} >/dev/null 2>&1 || true`,
      `docker build -q -f ../dashboard/Dockerfile -t ${IMAGE} ..`,
      // Detached plus `docker wait`: the process stays up for Playwright without
      // streaming Caddy's 502 log lines for the missing collector.
      `docker run -d --rm --name ${IMAGE} -p ${PORT}:8083 ${IMAGE} >/dev/null`,
      `docker wait ${IMAGE}`,
    ].join(' && '),
    url: `http://localhost:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
  },
})
