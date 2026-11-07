'use client';
import Link from 'next/link';
import { useRef,useState,type FormEvent } from 'react';
import { RecoveryFrame } from '@/components/recovery-frame';
import { Notice } from '@/components/ui';
import { useLanguage } from '@/lib/i18n';
import { api,messageOf,record } from '@/lib/api';
export default function ForgotPassword() {
  const {t}=useLanguage(),lock=useRef(false);
  const [busy,setBusy]=useState(false),[sent,setSent]=useState(false),[error,setError]=useState('');
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();if(lock.current)return;
    const email=String(new FormData(event.currentTarget).get('email')??'').trim();
    lock.current=true;setBusy(true);setError('');
    try {await api('/forgot-password',record,{email},30000);setSent(true);}
    catch(e){setError(messageOf(e));}
    finally{lock.current=false;setBusy(false);}
  }
  return <RecoveryFrame title={t('שכחת סיסמה?','Forgot your password?')} description={t('מזינים את המייל המאומת של החשבון ומקבלים קישור להגדרת סיסמה חדשה. הקישור תקף ל־30 דקות ולשימוש אחד.','Enter your verified account email to receive a password reset link. Links expire after 30 minutes and can be used once.')}>
    {sent?<><Notice>{t('אם המייל משויך לחשבון מאומת, נשלח אליו קישור איפוס. בדקו גם בתיקיית הספאם.','If this email belongs to a verified account, a reset link has been sent. Check your spam folder too.')}</Notice><button className="button ghost" onClick={()=>setSent(false)}>{t('שליחה נוספת או תיקון הכתובת','Send again or correct the address')}</button></>:<form onSubmit={submit} className="form-stack" aria-busy={busy}>
      {error&&<Notice error>{error}</Notice>}
      <div className="field"><label htmlFor="recovery-email">{t('מייל החשבון','Account email')}</label><input id="recovery-email" name="email" type="email" dir="ltr" autoComplete="email" maxLength={254} required disabled={busy}/></div>
      <button className="button primary full" disabled={busy}>{busy?t('שולחים…','Sending…'):t('שליחת קישור איפוס','Send reset link')}</button>
    </form>}
    <p>{t('חשבון ישן ללא מייל? אם אתם עדיין מחוברים, אפשר להוסיף ולאמת כתובת בעמוד החשבון.','Older account without email? If you are still signed in, add and verify an address in your account.')}</p><Link className="text-link" href="/account">{t('הגדרות החשבון','Account settings')}</Link>
  </RecoveryFrame>;
}
