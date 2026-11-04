'use client';
import Link from 'next/link';
import {Shell} from '@/components/ui';
import {useLanguage} from '@/lib/i18n';
export default function ErrorPage({unstable_retry}:{error:Error & {digest?:string};unstable_retry:()=>void}){
 const {t}=useLanguage();
 return <Shell><section className="app-empty"><h1>{t('אירעה תקלה בהצגת המסך','This screen could not be loaded')}</h1><p>{t('אפשר לנסות שוב או לחזור לדף הבית.','Try again or return to the home page.')}</p><div className="app-actions"><button className="button primary" onClick={unstable_retry}>{t('ניסיון חוזר','Try again')}</button><Link href="/" className="text-link">{t('חזרה לדף הבית','Back to home')}</Link></div></section></Shell>;
}
