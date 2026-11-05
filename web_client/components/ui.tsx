'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { api, record, money, messageOf, translateMessage, type User } from '@/lib/api';
import { LanguageSwitcher, useLanguage } from '@/lib/i18n';

export function Brand() {
  const {t} = useLanguage();
  return <Link href="/" className="brand" aria-label={t('Playoff Lab — דף הבית','Playoff Lab — Home')}>
    <svg className="brand-mark" width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="11" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 14h22M14 3v22M6 6c9 2 14 7 16 16M22 6C13 8 8 13 6 22" stroke="currentColor" strokeWidth="1.3"/>
    </svg>
    <span className="brand-name" dir="ltr">Playoff Lab</span>
  </Link>;
}

export function Shell({children, user}: {children: React.ReactNode; user?: User | null}) {
  const {t} = useLanguage();
  const path = usePathname(), router = useRouter();
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  async function logout() {
    if (pending) return;
    setPending(true); setError('');
    try {await api('/logout', record, {}); router.replace('/login');}
    catch(e) {setError(messageOf(e));}
    finally {setPending(false);}
  }
  const links = [
    {href:'/dashboard',he:'המגרש',en:'The court'},
    {href:'/bracket',he:'עץ הפלייאוף',en:'Playoff bracket'},
    {href:'/history',he:'ההימורים שלי',en:'My bets'},
  ];
  return <div className="app-shell">
    <a className="skip-link" href="#main">{t('דלג לתוכן','Skip to content')}</a>
    <header className="site-header"><div className="header-inner">
      <Brand/>
      <nav aria-label={t('ניווט ראשי','Main navigation')}>
        {links.map(link => <Link href={link.href} key={link.href} className={path === link.href ? 'active' : ''} aria-current={path === link.href ? 'page' : undefined}>{t(link.he,link.en)}</Link>)}
      </nav>
      <LanguageSwitcher/>
      {user && <div className="account">
        <span className="account-identity"><small dir="auto">{user.username}</small><span>{t('יתרה מדומה','Virtual balance')}</span></span>
        <strong dir="ltr">{money(user.balance)}</strong>
        <button className="icon-button" disabled={pending} onClick={() => void logout()} aria-label={t('התנתקות','Sign out')}>{pending ? t('יוצאים…','Signing out…') : t('יציאה','Sign out')}</button>
      </div>}
    </div></header>
    {error && <div className="container"><Notice error>{error}</Notice></div>}
    <main id="main" tabIndex={-1} className="container page-main">{children}</main>
    <footer className="site-footer"><div className="container app-footer-inner">
      <Brand/>
      <p>{t('טורניר אישי · יתרה מדומה בלבד','Personal tournament · Virtual funds only')}</p>
      <Link className="text-link" href="/accessibility">{t('הצהרת נגישות','Accessibility statement')}</Link>
    </div></footer>
  </div>;
}

export function Notice({children, error = false}: {children: React.ReactNode; error?: boolean}) {
  const {locale} = useLanguage();
  return <div className={`notice ${error ? 'notice-error' : ''}`} role={error ? 'alert' : 'status'}>{typeof children === 'string' ? translateMessage(children,locale) : children}</div>;
}

export function Loading() {
  const {t} = useLanguage();
  return <section className="app-loading" role="status" aria-live="polite">
    <h1>{t('טוענים את הנתונים','Loading your data')}</h1>
    <p>{t('הטורניר והיתרה שלך מתעדכנים.','Updating your tournament and balance.')}</p>
    <div className="loading-rows" aria-hidden="true"><span/><span/><span/></div>
  </section>;
}

export function LoadError({message, retry}: {message: string; retry: () => void}) {
  const {t} = useLanguage();
  return <section className="app-empty">
    <h1>{t('הנתונים לא נטענו','Your data could not be loaded')}</h1>
    <Notice error>{message}</Notice>
    <div className="app-actions"><button className="button primary" onClick={retry}>{t('ניסיון חוזר','Try again')}</button><Link href="/login" className="text-link">{t('מעבר להתחברות','Go to sign in')}</Link></div>
  </section>;
}

export function TeamBadge({name, small = false}: {name: string; small?: boolean}) {
  const initials = name === 'TBD' ? '—' : name.split(' ').filter(Boolean).slice(-2).map(s => s[0]).join('');
  return <span className={`team-badge ${small ? 'small' : ''}`} aria-hidden="true">{initials}</span>;
}

export function ConfirmDialog({busy, error, confirm, cancel}: {busy: boolean; error?: string; confirm: () => void; cancel: () => void}) {
  const {t} = useLanguage();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {const dialog = ref.current; dialog?.showModal(); return () => dialog?.close();}, []);
  return <dialog ref={ref} className="confirm-dialog native-dialog" aria-labelledby="reset-title" aria-describedby="reset-description" onCancel={event => {event.preventDefault(); if (!busy) cancel();}}>
    <h2 id="reset-title">{t('פתיחת עונה חדשה','Start a new season')}</h2>
    <p id="reset-description">{t('תוצאות העונה הנוכחית יאורכבו. הימורים פתוחים יבוטלו ויוחזרו ליתרה. ההיסטוריה תישמר.','The current season will be archived. Open bets will be cancelled and refunded. Your history will be preserved.')}</p>
    {error && <Notice error>{error}</Notice>}
    <div className="app-actions"><button className="button primary" disabled={busy} onClick={confirm}>{busy ? t('פותחים עונה…','Starting season…') : t('אישור ופתיחת עונה','Start new season')}</button><button autoFocus className="button ghost" disabled={busy} onClick={cancel}>{t('ביטול','Cancel')}</button></div>
  </dialog>;
}
