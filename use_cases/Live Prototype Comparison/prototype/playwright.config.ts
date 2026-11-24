import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  projects: [
    { name: 'design-a', testIgnore: /board\.spec\.ts$/ },
    { name: 'design-b', testIgnore: /board\.spec\.ts$/ },
    { name: 'design-c', testIgnore: /board\.spec\.ts$/ },
    { name: 'design-d', testMatch: /board\.spec\.ts$/ },
  ],
  use: {
    baseURL: 'http://127.0.0.1:4174',
    channel: 'msedge',
    viewport: { width: 1440, height: 960 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4174 --strictPort',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: !process.env.CI,
  },
})
