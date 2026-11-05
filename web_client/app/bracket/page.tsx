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

const rounds = [
  {key: 'r1', he: 'סיבוב ראשון', en: 'First round'},
  {key: 'r2', he: 'חצי גמר אזורי', en: 'Conference semifinals'},
  {key: 'r3', he: 'גמר אזורי', en: 'Conference finals'},
] as const;

function Connectors() {
  return <svg className="bracket-connectors" viewBox="0 0 700 400" preserveAspectRatio="none" aria-hidden="true" focusable="false">
    <path className="bracket-court" d="M350 0V400 M397 200a47 47 0 1 0-94 0 47 47 0 1 0 94 0 M0 108H112V292H0 M700 108H588V292H700"/>
    <path className="bracket-west-lines" d="M50 50H100V150H50 M100 100H150 M50 250H100V350H50 M100 300H150 M150 100H200V300H150 M200 200H250"/>
    <path className="bracket-east-lines" d="M650 50H600V150H650 M600 100H550 M650 250H600V350H650 M600 300H550 M550 100H500V300H550 M500 200H450"/>
    <path className="bracket-final-lines" d="M250 200H450"/>
  </svg>;
}

export default function BracketPage() {
  const {t,locale} = useLanguage();
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
    <div className="bracket-board" tabIndex={0} role="region" dir="ltr" aria-label={t('עץ הפלייאוף המלא, מערב, גמר ומזרח','Full playoff bracket, West, Finals and East')}>
      <div className="bracket-stage">
        <Connectors/>
        {(['west', 'finals', 'east'] as const).map(side => {
          const dir = locale === 'he' ? 'rtl' : 'ltr';
          if (side === 'finals') return <section key={side} className="bracket-center" aria-labelledby="finals-title">
            <h2 id="finals-title" dir={dir}>{t('גמר NBA','NBA Finals')}</h2>
            <div className="bracket-center-match" dir={dir}>
              <Match match={bracket.finals}/>
              {bracket.champion && <p className="bracket-champion">{t('אלופה','Champion')} <bdi>{bracket.champion}</bdi></p>}
            </div>
          </section>;
          return <section className={`bracket-wing bracket-${side}`} key={side} aria-labelledby={`conference-${side}`}>
            <h2 id={`conference-${side}`} dir={dir}>{side === 'west' ? t('המערב','West') : t('המזרח','East')}</h2>
            <div className="bracket-wing-rounds">
              {rounds.map(round => <div className={`bracket-column bracket-${round.key}`} key={round.key} dir={dir}>
                <h3>{t(round.he, round.en)}</h3>
                <div className="bracket-pairs">{bracket[side][round.key].map((match, slot) => <Match key={slot} match={match}/>)}</div>
              </div>)}
            </div>
          </section>;
        })}
      </div>
    </div>
  </Shell>;
}
