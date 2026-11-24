import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { translate, type Locale } from './state'

interface LocaleContextValue {
  language: Locale
  setLanguage: (language: Locale) => void
  t: (chinese: string, english?: string) => string
  storageError: boolean
}
const LocaleContext = createContext<LocaleContextValue | null>(null)

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [loaded] = useState(() => {
    try {
      const saved = localStorage.getItem('dayline-language')
      return { language: saved === 'zh' ? 'zh' as const : 'en' as const, error: false }
    } catch (error) {
      console.error('Unable to read language preference', error)
      return { language: 'en' as const, error: true }
    }
  })
  const [language, setLanguage] = useState<Locale>(loaded.language)
  const [storageError, setStorageError] = useState(loaded.error)
  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
    try { localStorage.setItem('dayline-language', language) }
    catch (error) {
      console.error('Unable to save language preference', error)
      setStorageError(true)
    }
  }, [language])
  return <LocaleContext.Provider value={{
    language, setLanguage, storageError,
    t: (chinese, english) => language === 'zh' ? chinese : english ?? translate(chinese, 'en'),
  }}>{children}</LocaleContext.Provider>
}

export function useLocale() {
  const context = useContext(LocaleContext)
  if (!context) throw new Error('LocaleProvider is required.')
  return context
}
