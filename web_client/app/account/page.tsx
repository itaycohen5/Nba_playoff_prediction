'use client';
import { useRef,useState,type FormEvent } from 'react';
import { api,record,text,parseUser,messageOf } from '@/lib/api';
import { useLanguage } from '@/lib/i18n';
import { useProtected } from '@/lib/use-protected';
import { Shell,Loading,LoadError,Notice } from '@/components/ui';
async function load(signal?:AbortSignal){
  const [user,email]=await Promise.all([api('/me',parseUser,undefined,15000,signal),api('/me/email',value=>{
    const r=record(value);
    if(typeof r.verified!=='boolean'||typeof r.delivery_configured!=='boolean')throw new Error('Invalid email status');
    return {address:r.email===null?null:text(r.email),verified:r.verified,configured:r.delivery_configured};
  },undefined,15000,signal)]);
  return {user,email};
}
export default function Account(){
  const {t}=useLanguage(),{data,error,loading,refresh}=useProtected(load),lock=useRef(false);
  const [busy,setBusy]=useState(false),[sent,setSent]=useState(false),[failure,setFailure]=useState('');
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();if(lock.current)return;
    const form=event.currentTarget,values=new FormData(form);
    lock.current=true;setBusy(true);setFailure('');setSent(false);
    try{await api('/me/email',record,{email:String(values.get('email')??'').trim(),password:String(values.get('password')??'')},30000);form.reset();setSent(true);await refresh();}
    catch(e){setFailure(messageOf(e));}
    finally{lock.current=false;setBusy(false);}
  }
  if(loading)return <Shell><Loading/></Shell>;
  if(!data)return <Shell><LoadError message={error} retry={()=>void refresh()}/></Shell>;
  return <Shell user={data.user}>
    <header className="app-title-row"><div><h1>{t('החשבון שלי','My account')}</h1><p>{t('מייל מאומת לשחזור סיסמה','Verified email for password recovery')}</p></div></header>
    <section className="auth-form-section" aria-labelledby="email-settings-title">
      <h2 id="email-settings-title">{t('כתובת המייל','Email address')}</h2>
      <p dir="auto">{data.email.address??t('טרם נוספה כתובת','No address added yet')}</p>
      <p role="status">{data.email.verified?t('✓ המייל מאומת','✓ Email verified'):t('המייל עדיין לא אומת','Email not yet verified')}</p>
      {!data.email.configured&&<Notice error>{t('שליחת המיילים עדיין לא הוגדרה בשרת. יש להשלים את ההגדרה לפני אימות או שחזור.','Email delivery is not configured on the server yet. Complete setup before verification or recovery.')}</Notice>}
      {error&&<Notice error>{error}</Notice>}{failure&&<Notice error>{failure}</Notice>}{sent&&<Notice>{t('נשלח קישור אימות. פתחו אותו במייל ואשרו את הכתובת.','A verification link was sent. Open it in your email and confirm the address.')}</Notice>}
      <form onSubmit={submit} className="form-stack" aria-busy={busy}>
        <div className="field"><label htmlFor="account-email">{t('מייל לשחזור החשבון','Recovery email')}</label><input id="account-email" name="email" type="email" dir="ltr" autoComplete="email" maxLength={254} defaultValue={data.email.address??''} required disabled={busy}/></div>
        <div className="field"><label htmlFor="account-password">{t('הסיסמה הנוכחית','Current password')}</label><input id="account-password" name="password" type="password" autoComplete="current-password" required disabled={busy}/></div>
        <button className="button primary" disabled={busy||!data.email.configured}>{busy?t('שולחים…','Sending…'):t('שמירה ושליחת קישור אימות','Save and send verification link')}</button>
      </form>
    </section>
  </Shell>;
}
