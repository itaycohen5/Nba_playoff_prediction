'use client';
import './taste-app.css';
import './taste-dashboard.css';
import './taste-page.css';
import './accessibility.css';
import Link from 'next/link';
import { SitePreferences } from '@/components/site-preferences';
import { LanguageSwitcher, useLanguage } from '@/lib/i18n';
function GlobalErrorScreen({retry}: {retry: () => void}) {
  const {t} = useLanguage();
  return <div style={{padding:'7vh 24px',background:'#0b1120',color:'#f4f2eb',fontFamily:'Arial, sans-serif',textAlign:'center',minHeight:'100vh'}}><header style={{display:'flex',justifyContent:'center',marginBottom:40}}><LanguageSwitcher/></header><main id="main" tabIndex={-1}><h1>{t('אירעה תקלה בטעינת המגרש','We could not load the court')}</h1><p>{t('אפשר לנסות שוב.','Please try again.')}</p><button style={{padding:'12px 24px',cursor:'pointer'}} onClick={retry}>{t('ניסיון חוזר','Try again')}</button> <Link style={{color:'#f4c469'}} href="/">{t('דף הבית','Home')}</Link></main><footer style={{marginTop:30}}><Link href="/accessibility">{t('הצהרת נגישות','Accessibility statement')}</Link></footer></div>;
}
export default function GlobalError({unstable_retry}: {error: Error & {digest?: string}; unstable_retry: () => void}) {
  return <html lang="he" dir="rtl"><body style={{margin:0}}><SitePreferences><GlobalErrorScreen retry={unstable_retry}/></SitePreferences></body></html>;
}
