'use client';

import Link from 'next/link';
import { useRef, useState, type FormEvent } from 'react';
import { Brand, Notice } from '@/components/ui';
import { LanguageSwitcher, useLanguage } from '@/lib/i18n';
import { api, messageOf, record } from '@/lib/api';
import { PasswordRules, passwordIssues } from '@/components/password-rules';

export default function ResetPasswordPage() {
  const {t} = useLanguage();
  const submitting = useRef(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [password, setPassword] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const form = new FormData(event.currentTarget);
    const code = String(form.get('code') ?? '').trim();
    if (!/^[A-Za-z0-9_-]{43}$/.test(code)) {
      setError('קוד האיפוס אינו תקף או שפג תוקפו');
      return;
    }
    const missing = passwordIssues(password, t);
    if (missing.length) {
      setError(t('דרישות סיסמה חסרות: ', 'Missing password requirements: ') + missing.join(' · '));
      return;
    }
    if (new TextEncoder().encode(password).length > 72) {
      setError('נדרשת סיסמה עם לפחות 8 תווים ועד 72 בתים (תווים בעברית תופסים יותר מבית אחד)');
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
        <p>{t('בקשו ממנהל האתר קוד איפוס לאחר אימות בעלות. הקוד תקף ל־30 דקות ולשימוש אחד.', 'Request a reset code from the site administrator after verifying ownership. The code expires after 30 minutes and can only be used once.')}</p>
      </section>
      <section className="auth-form-section" aria-labelledby="reset-title">
        <h1 id="reset-title">{t('איפוס סיסמה','Reset password')}</h1>
        {done ? <Notice>{t('הסיסמה עודכנה. אפשר להתחבר עם הסיסמה החדשה.','Password updated. Sign in with your new password.')}</Notice> :
          <form onSubmit={submit} className="form-stack" aria-busy={busy}>
            {error && <Notice error>{error}</Notice>}
            <div className="field"><label htmlFor="reset-code">{t('קוד איפוס','Reset code')}</label><input id="reset-code" name="code" dir="ltr" autoComplete="one-time-code" spellCheck={false} required disabled={busy}/></div>
            <div className="field"><label htmlFor="new-password">{t('סיסמה חדשה','New password')}</label><input id="new-password" name="password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" required disabled={busy} aria-describedby="reset-password-help"/><PasswordRules id="reset-password-help" value={password}/></div>
            <div className="field"><label htmlFor="confirm-password">{t('אימות סיסמה','Confirm password')}</label><input id="confirm-password" name="confirm" type="password" autoComplete="new-password" required disabled={busy}/></div>
            <button className="button primary full" disabled={busy}>{busy ? t('שומרים…','Saving…') : t('שמירת סיסמה','Save password')}</button>
          </form>}
        <p className="auth-switch"><Link href="/login">{t('חזרה לכניסה','Back to sign in')}</Link></p>
      </section>
    </main>
  </div>;
}
