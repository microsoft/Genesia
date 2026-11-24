import { defineConfig } from '@playwright/test'
import base from './playwright.config'

export default defineConfig({
  ...base,
  use: {
    ...base.use,
    reducedMotion: 'reduce',
  },
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4174 --strictPort',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
  },
})
