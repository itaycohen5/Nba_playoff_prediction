'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
export type Locale = 'he' | 'en';
interface LanguageContextValue {locale: Locale; t: (he: string, en: string) => string; setLocale: (locale: Locale) => void}
const LanguageContext = createContext<LanguageContextValue>({locale:'he',t:he=>he,setLocale:()=>{}});
export function LanguageProvider({children}: {children: React.ReactNode}) {
  const [locale, updateLocale] = useState<Locale>('he');
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (!active) return;
      try {const saved = localStorage.getItem('playoff-language'); if (saved === 'he' || saved === 'en') updateLocale(saved);} catch {}
    });
    return () => {active = false;};
  }, []);
  const setLocale = useCallback((next: Locale) => {
    updateLocale(next);
    try {localStorage.setItem('playoff-language', next);} catch {}
  }, []);
  useEffect(() => {document.documentElement.lang = locale; document.documentElement.dir = locale === 'he' ? 'rtl' : 'ltr'; document.title = locale === 'he' ? 'Playoff Lab | מעבדת הפלייאוף שלך' : 'Playoff Lab | Your personal playoff simulator';}, [locale]);
  const value = useMemo(() => ({locale,setLocale,t:(he: string,en: string)=>locale === 'he' ? he : en}), [locale,setLocale]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
export const useLanguage = () => useContext(LanguageContext);
export function LanguageSwitcher() {
  const {locale,setLocale,t} = useLanguage();
  return <div className="language-switcher" role="group" aria-label={t('בחירת שפה','Choose language')} dir="ltr"><button type="button" lang="he" aria-pressed={locale === 'he'} onClick={() => setLocale('he')}>עברית</button><span aria-hidden="true">/</span><button type="button" lang="en" aria-pressed={locale === 'en'} onClick={() => setLocale('en')}>EN</button></div>;
}
