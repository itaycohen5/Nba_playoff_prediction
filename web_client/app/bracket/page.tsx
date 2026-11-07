'use client';
import Link from 'next/link';
import { PlayoffBracket } from '@/components/playoff-bracket';
import { useLanguage } from '@/lib/i18n';
import { api, parseUser, parseBracket } from '@/lib/api';
import { useProtected } from '@/lib/use-protected';
import { Shell, Loading, LoadError, Notice } from '@/components/ui';

async function load(signal?: AbortSignal) {
  const [user,bracket] = await Promise.all([api('/me',parseUser,undefined,15000,signal),api('/tournament-status',parseBracket,undefined,15000,signal)]);
  return {user,bracket};
}

export default function BracketPage() {
  const {t} = useLanguage();
  const {data,error,loading,refresh} = useProtected(load);
  if (loading) return <Shell><Loading/></Shell>;
  if (!data) return <Shell><LoadError message={error} retry={() => void refresh()}/></Shell>;
  const {user,bracket} = data;
  return <Shell user={user}>
    <header className="app-title-row"><div><h1>{t('עץ הפלייאוף','Playoff bracket')}</h1><p>{t('ארבעה ניצחונות בסדרה כדי לעלות שלב. התוצאות שייכות לטורניר האישי שלך.','Four wins to advance. Results belong to your personal tournament.')}</p></div><button className="button ghost" onClick={() => void refresh()}>{t('רענון תוצאות','Refresh results')}</button></header>
    {error && <Notice error>{error}</Notice>}
    <div className="bracket-scroll-hint">
      <span>{t('במסך צר אפשר לגלול לצדדים כדי לראות את כל העץ.','Scroll sideways on a narrow screen to see the whole bracket.')}</span>
      <Link className="text-link" href="/dashboard">{t('חזרה למגרש','Back to the court')}</Link>
    </div>
    <PlayoffBracket bracket={bracket}/>
  </Shell>;
}
