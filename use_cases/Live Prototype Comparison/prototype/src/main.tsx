import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { LocaleProvider } from './i18n/LocaleProvider'
import './styles.css'
import './design-b.css'
import './design-c.css'
import './design-d.css'
import './contrast-fix.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LocaleProvider><App /></LocaleProvider>
  </StrictMode>,
)
