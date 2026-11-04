'use client';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import { api, parseUser, parseBracket, type Matchup } from '@/lib/api';
import { useProtected } from '@/lib/use-protected';
import { Shell, Loading, LoadError, Notice, TeamBadge } from '@/components/ui';

async function load(signal?: AbortSignal) {
  const [user,bracket] = await Promise.all([api('/me',parseUser,undefined,15000,signal),api('/tournament-status',parseBracket,undefined,15000,signal)]);
  return {user,bracket};
}

function Match({match}: {match: Matchup}) {
  const {t} = useLanguage();
  const teamName = (name:string) => name === 'TBD' ? t('טרם נקבע','To be decided') : name;
  return <article className="bracket-match" aria-label={`${teamName(match.t1.name)} ${match.t1.wins} — ${match.t2.wins} ${teamName(match.t2.name)}`}>
    {[match.t1,match.t2].map((team,index) => <div className={team.wins >= 4 ? 'winner' : ''} key={index}>
      <TeamBadge name={team.name} small/>
      <span dir="auto">{teamName(team.name)}{team.wins >= 4 && <span className="visually-hidden"> · {t('מנצחת הסדרה','Series winner')}</span>}</span>
      <strong>{team.wins}</strong>
    </div>)}
  </article>;
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
    <section className={`bracket-finals ${bracket.champion ? 'has-champion' : ''}`} aria-labelledby="finals-title">
      <div className="bracket-finals-caption"><h2 id="finals-title">{bracket.champion ? t('אלופת הטורניר','Tournament champion') : t('גמר NBA','NBA Finals')}</h2>{bracket.champion ? <p className="bracket-champion" dir="auto">{bracket.champion}</p> : <p>{t('אלופת המערב מול אלופת המזרח','West champion versus East champion')}</p>}<Link className="text-link" href="/dashboard">{t('חזרה למגרש','Back to the court')}</Link></div>
      <Match match={bracket.finals}/>
    </section>
    <div className="bracket-conferences">
      {([{key:'west',title:t('המערב','Western Conference')},{key:'east',title:t('המזרח','Eastern Conference')}] as const).map(({key,title}) => <section className="bracket-conference" key={key} aria-labelledby={`conference-${key}`}>
        <h2 id={`conference-${key}`}>{title}</h2>
        <div className="bracket-scroll" tabIndex={0} role="region" aria-label={t(`שלבי ${title}. אפשר לגלול אופקית במסך קטן.`,`${title} rounds. Scroll horizontally on a small screen.`)}>
          <div className="bracket-track">{([{key:'r1',title:t('סיבוב ראשון','First round')},{key:'r2',title:t('חצי גמר אזורי','Conference semifinals')},{key:'r3',title:t('גמר אזורי','Conference finals')}] as const).map(round => <div className={`bracket-round round-${round.key}`} key={round.key}>
            <h3>{round.title}</h3>
            <div className="round-matches">{bracket[key][round.key].map((match,index) => <Match key={index} match={match}/>)}</div>
          </div>)}</div>
        </div>
      </section>)}
    </div>
  </Shell>;
}
