'use client';

import Link from 'next/link';
import { useRef, useState, type FormEvent } from 'react';
import { Brand, Notice } from '@/components/ui';
import { LanguageSwitcher, useLanguage } from '@/lib/i18n';
import { api, messageOf, record } from '@/lib/api';
import { PasswordPolicyNotice, PasswordRules, meetsPasswordRules, passwordPolicyError } from '@/components/password-rules';
import { useLinkToken } from '@/lib/use-link-token';

export default function ResetPasswordPage() {
  const {t} = useLanguage();
  const code = useLinkToken();
  const submitting = useRef(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [password, setPassword] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const form = new FormData(event.currentTarget);
    if (!code) {
      setError('קוד האיפוס אינו תקף או שפג תוקפו');
      return;
    }
    if (!meetsPasswordRules(password)) {
      setError(passwordPolicyError);
      return;
    }
    if (password !== form.get('confirm')) {
      setError('הסיסמאות אינן תואמות');
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      await api('/reset-password', record, {code, password});
      setDone(true);
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return <div className="app-auth">
    <a className="skip-link" href="#main">{t('דלג לתוכן','Skip to content')}</a>
    <header className="auth-header"><Brand/><LanguageSwitcher/></header>
    <main id="main" tabIndex={-1} className="auth-layout">
      <section className="auth-context">
        <h2>{t('שחזור חשבון','Account recovery')}</h2>
        <p>{t('בחרו סיסמה חדשה ואמתו אותה. הקישור מהמייל תקף ל־30 דקות ולשימוש אחד.', 'Choose and confirm a new password. Your email link expires after 30 minutes and can only be used once.')}</p>
      </section>
      <section className="auth-form-section" aria-labelledby="reset-title">
        <h1 id="reset-title">{t('איפוס סיסמה','Reset password')}</h1>
        {done ? <Notice>{t('הסיסמה עודכנה. אפשר להתחבר עם הסיסמה החדשה.','Password updated. Sign in with your new password.')}</Notice> : code === null ? <p role="status">{t('בודקים את הקישור…','Reading the link…')}</p> : !code ? <><Notice error>{t('יש לפתוח את קישור האיפוס שקיבלתם במייל.','Open the reset link from your email.')}</Notice><Link className="button primary" href="/forgot-password">{t('בקשת קישור חדש','Request a new link')}</Link></> :
          <form onSubmit={submit} className="form-stack" aria-busy={busy}>
            {error === passwordPolicyError ? <PasswordPolicyNotice value={password}/> : error && <Notice error>{error}</Notice>}
            <div className="field"><label htmlFor="new-password">{t('סיסמה חדשה','New password')}</label><input id="new-password" name="password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" required disabled={busy} aria-describedby="reset-password-help"/><PasswordRules id="reset-password-help" value={password}/></div>
            <div className="field"><label htmlFor="confirm-password">{t('אימות סיסמה','Confirm password')}</label><input id="confirm-password" name="confirm" type="password" autoComplete="new-password" required disabled={busy}/></div>
            <button className="button primary full" disabled={busy}>{busy ? t('שומרים…','Saving…') : t('שמירת סיסמה','Save password')}</button>
          </form>}
        <p className="auth-switch"><Link href="/login">{t('חזרה לכניסה','Back to sign in')}</Link></p>
        <p className="auth-switch"><Link href="/forgot-password">{t('הקישור פג? בקשת קישור חדש','Link expired? Request another')}</Link></p>
      </section>
    </main>
    <footer className="auth-bottom"><Link href="/accessibility" className="text-link">{t('הצהרת נגישות','Accessibility statement')}</Link></footer>
  </div>;
}
