'use client';
import Link from 'next/link';
import { useRef,useState } from 'react';
import { RecoveryFrame } from '@/components/recovery-frame';
import { Notice } from '@/components/ui';
import { useLanguage } from '@/lib/i18n';
import { useLinkToken } from '@/lib/use-link-token';
import { api,record,messageOf } from '@/lib/api';
export default function VerifyEmail() {
  const {t}=useLanguage(),token=useLinkToken(),lock=useRef(false);
  const [busy,setBusy]=useState(false),[done,setDone]=useState(false),[error,setError]=useState('');
  async function verify(){
    if(lock.current||!token)return;
    lock.current=true;setBusy(true);setError('');
    try{await api('/verify-email',record,{code:token});setDone(true);}
    catch(e){setError(messageOf(e));}
    finally{lock.current=false;setBusy(false);}
  }
  return <RecoveryFrame title={t('אימות המייל','Verify your email')} description={t('אימות הכתובת מאפשר לקבל אליה קישור איפוס סיסמה באופן עצמאי.','Verifying your address enables self-service password recovery.')}>
    {error&&<Notice error>{error}</Notice>}
    {done?<Notice>{t('המייל אומת בהצלחה. אפשר להשתמש בו לשחזור החשבון.','Your email is verified and ready for account recovery.')}</Notice>:token===null?<p role="status">{t('בודקים את הקישור…','Reading the link…')}</p>:!token?<Notice error>{t('הקישור חסר או לא תקין. בקשו קישור חדש מעמוד החשבון.','The link is missing or invalid. Request another from your account.')}</Notice>:<button className="button primary full" disabled={busy} onClick={()=>void verify()}>{busy?t('מאמתים…','Verifying…'):t('אישור ואימות המייל שלי','Confirm and verify my email')}</button>}
    <p><Link className="text-link" href="/account">{t('מעבר לחשבון או שליחת קישור חדש','Account settings or request a new link')}</Link></p>
  </RecoveryFrame>;
}
