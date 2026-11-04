'use client';
import Link from 'next/link';
import {Shell} from '@/components/ui';
import {useLanguage} from '@/lib/i18n';
export default function NotFound(){const {t}=useLanguage();return <Shell><section className="app-empty"><h1>{t('העמוד לא נמצא','Page not found')}</h1><p>{t('הכתובת אינה קיימת. אפשר לחזור למגרש או לדף הבית.','This address does not exist. Return to the court or the home page.')}</p><div className="app-actions"><Link className="button primary" href="/dashboard">{t('למגרש','To the court')}</Link><Link className="text-link" href="/">{t('דף הבית','Home')}</Link></div></section></Shell>;}
