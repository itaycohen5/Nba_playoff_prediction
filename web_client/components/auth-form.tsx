'use client';
import Link from 'next/link';
import { useLanguage, LanguageSwitcher } from '@/lib/i18n';
import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';
import { api, parseUser, messageOf } from '@/lib/api';
import { Brand, Notice } from './ui';

export function AuthForm({register = false}: {register?: boolean}) {
  const {t} = useLanguage();
  const router = useRouter(), lock = useRef(false);
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [confirm, setConfirm] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (lock.current) return; setError('');
    const name = username.trim(), bytes = new TextEncoder().encode(password).length;
    if (!name) {setError('יש להזין שם משתמש'); return;}
    if (register && !/^[\p{L}\p{N}_]{3,40}$/u.test(name)) {setError('שם משתמש: 3–40 אותיות, ספרות או קו תחתון, ללא רווחים'); return;}
    if (register && Array.from(password).length < 8) {setError(t('נדרשת סיסמה עם לפחות 8 תווים','Use a password with at least 8 characters')); return;}
    if (bytes > 72) {setError(t('הסיסמה ארוכה מדי. נסו לקצר אותה.','This password is too long. Try a shorter one.')); return;}
    if (!password.length) {setError(t('יש להזין סיסמה','Enter your password')); return;}
    if (register && password !== confirm) {setError('הסיסמאות אינן תואמות'); return;}
    lock.current = true; setBusy(true);
    try {
      await api(register ? '/register' : '/login', parseUser, {username:name,password});
      try {localStorage.removeItem('userId');} catch {}
      router.replace('/dashboard');
    } catch(e) {setError(messageOf(e));}
    finally {lock.current = false; setBusy(false);}
  }
  return <div className="app-auth">
    <a className="skip-link" href="#main">{t('דלג לתוכן','Skip to content')}</a>
    <header className="auth-header"><Brand/><LanguageSwitcher/></header>
    <main id="main" tabIndex={-1} className="auth-layout">
      <section className="auth-context" aria-labelledby="auth-context-title">
        <h2 id="auth-context-title">{t('הפלייאוף שלך. בקצב שלך.','Your playoffs. Your pace.')}</h2>
        <p>{t('מהסדרה הראשונה עד הגמר: בוחרים תחזית, מריצים משחק ומשווים לתוצאה. לכל חשבון טורניר אישי שנשמר גם בפעם הבאה.','From the opening series to the finals: make your pick, simulate a game and compare the result. Each account has a private tournament, ready for your next visit.')}</p>
        <dl className="auth-format"><div><dt>{t('הפורמט','Format')}</dt><dd>{t('16 קבוצות · הטוב מ־7','16 teams · Best of seven')}</dd></div><div><dt>{t('יתרת פתיחה','Starting balance')}</dt><dd><bdi>$1,000.00</bdi> {t('מדומים','virtual')}</dd></div><div><dt>{t('הנתונים','Data')}</dt><dd>{t('נתוני עונה שמורים · סימולציה סטטיסטית','Saved season data · Statistical simulation')}</dd></div></dl>
        <Link href="/" className="text-link">{t('חזרה לדף הבית','Back to home')}</Link>
      </section>
      <section className="auth-form-section" aria-labelledby="auth-title">
        <h1 id="auth-title">{register ? t('יצירת חשבון','Create an account') : t('כניסה לחשבון','Sign in')}</h1>
        <p className="auth-description">{register ? t('פותחים טורניר אישי עם יתרה מדומה.','Start your personal tournament with virtual funds.') : t('ממשיכים מהסדרה שבה עצרת.','Pick up where your last series left off.')}</p>
        <form onSubmit={submit} className="form-stack" aria-busy={busy}>
          {error && <Notice error>{error}</Notice>}
          <div className="field">
            <label htmlFor="username">{t('שם משתמש','Username')}</label>
            <input id="username" name="username" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" minLength={register ? 3 : 1} maxLength={40} required disabled={busy} aria-describedby={register ? 'username-help' : undefined}/>
            {register && <small id="username-help">{t('3–40 אותיות, ספרות או קו תחתון.','3–40 letters, numbers or underscores.')}</small>}
          </div>
          <div className="field"><label htmlFor="password">{t('סיסמה','Password')}</label><input id="password" name="password" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 8 : 1} required disabled={busy} aria-describedby={register ? 'password-help' : undefined}/>{register && <small id="password-help">{t('לפחות 8 תווים. אפשר להשתמש במשפט קצר.','At least 8 characters. A short phrase works well.')}</small>}</div>
          {register && <div className="field"><label htmlFor="confirm">{t('אימות סיסמה','Confirm password')}</label><input id="confirm" name="confirm" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="new-password" required disabled={busy}/></div>}
          <button className="button primary full" disabled={busy}>{busy ? t('מתחברים…','Signing you in…') : register ? t('יצירת חשבון','Create account') : t('כניסה לחשבון','Sign in')}</button>
        </form>
        {!register && <p className="auth-switch"><Link href="/reset-password">{t('שכחת סיסמה?','Forgot your password?')}</Link></p>}
        <p className="auth-switch">{register ? t('כבר יש לך חשבון?','Already have an account?') : t('אין לך חשבון עדיין?','No account yet?')} <Link href={register ? '/login' : '/register'}>{register ? t('כניסה','Sign in') : t('יצירת חשבון','Create an account')}</Link></p>
      </section>
    </main>
    <footer className="auth-bottom"><p>{t('סימולציה בלבד. אין שימוש בכסף אמיתי.','Simulation only. No real money is used.')}</p><Link href="/accessibility" className="text-link">{t('הצהרת נגישות','Accessibility statement')}</Link></footer>
  </div>;
}
