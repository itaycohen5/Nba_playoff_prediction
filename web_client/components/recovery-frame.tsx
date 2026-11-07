'use client';
import Link from 'next/link';
import { Brand } from './ui';
import { LanguageSwitcher, useLanguage } from '@/lib/i18n';
export function RecoveryFrame({title, description, children}: {title:string; description:string; children:React.ReactNode}) {
  const {t}=useLanguage();
  return <div className="app-auth">
    <a className="skip-link" href="#main">{t('דלג לתוכן','Skip to content')}</a>
    <header className="auth-header"><Brand/><LanguageSwitcher/></header>
    <main id="main" tabIndex={-1} className="auth-layout">
      <section className="auth-context"><h2>{t('חוזרים למגרש','Back to the court')}</h2><p>{description}</p></section>
      <section className="auth-form-section" aria-labelledby="recovery-title"><h1 id="recovery-title">{title}</h1>{children}<p className="auth-switch"><Link href="/login">{t('חזרה לכניסה','Back to sign in')}</Link></p></section>
    </main>
    <footer className="auth-bottom"><Link className="text-link" href="/accessibility">{t('הצהרת נגישות','Accessibility statement')}</Link></footer>
  </div>;
}
