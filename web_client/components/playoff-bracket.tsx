'use client';
import { useId,type CSSProperties } from 'react';
import { Trophy } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';
import { type Bracket,type Matchup } from '@/lib/api';
import { TeamLogo,teamBrand } from './team-logo';

export function PlayoffMatch({match}:{match:Matchup}) {
  const {t}=useLanguage();
  const label=(name:string)=>name==='TBD'?t('טרם נקבע','To be decided'):name;
  return <article className="playoff-match" aria-label={label(match.t1.name)+' '+match.t1.wins+' — '+match.t2.wins+' '+label(match.t2.name)}>
    {[match.t1,match.t2].map((team,index)=>{
      const brand=teamBrand(team.name),unknown=team.name==='TBD',won=team.wins>=4;
      return <div className="playoff-team" data-winner={won} data-empty={unknown} style={{'--team-color':brand?.color??'#58708f','--team-mark':brand?'url("'+brand.logo+'")':'none'} as CSSProperties} key={index}>
        <span className="playoff-seed" aria-label={t('דירוג','Seed')}>{brand?.seed??'—'}</span>
        <TeamLogo name={team.name}/>
        <span className="playoff-team-name" dir="ltr"><small>{brand?.city??''}</small><b>{brand?.nickname??label(team.name)}</b></span>
        <strong className="playoff-score" aria-label={t('ניצחונות בסדרה','Series wins')}>{unknown?'—':team.wins}</strong>
        {won&&<span className="visually-hidden">{t('מנצחת הסדרה','Series winner')}</span>}
      </div>;
    })}
  </article>;
}
const rounds=[{key:'r1',he:'סיבוב ראשון',en:'First round'},{key:'r2',he:'חצי גמר אזורי',en:'Conference semifinals'},{key:'r3',he:'גמר אזורי',en:'Conference finals'}] as const;
function Connectors(){
  return <svg className="bracket-connectors" viewBox="0 0 700 400" preserveAspectRatio="none" aria-hidden="true" focusable="false">
    <path className="bracket-west-lines" d="M50 50H100V150H50 M100 100H150 M50 250H100V350H50 M100 300H150 M150 100H200V300H150 M200 200H250"/>
    <path className="bracket-east-lines" d="M650 50H600V150H650 M600 100H550 M650 250H600V350H650 M600 300H550 M550 100H500V300H550 M500 200H450"/>
    <path className="bracket-final-lines" d="M250 200H450"/>
  </svg>;
}
export function PlayoffBracket({bracket,preview=false}:{bracket:Bracket;preview?:boolean}){
  const {t,locale}=useLanguage(),id=useId(),dir=locale==='he'?'rtl':'ltr';
  return <div className="bracket-board playoff-bracket" data-preview={preview} tabIndex={0} role="region" dir="ltr" aria-label={t('עץ הפלייאוף: מערב משמאל, מזרח מימין וגמר במרכז. ניתן לגלול לצדדים.','Playoff bracket: West on the left, East on the right, Finals in the center. Scroll horizontally.')}>
    <div className="bracket-stage">
      <Connectors/>
      {(['west','finals','east'] as const).map(side=>{
        if(side==='finals')return <section key={side} className="bracket-center" aria-labelledby={id+'-finals'}>
          <h2 id={id+'-finals'} className="playoff-wordmark"><span>NBA</span><b>PLAYOFFS</b></h2>
          <div className="bracket-center-match"><div className="playoff-finals-block">
            <Trophy size={38} strokeWidth={1.4} aria-hidden="true"/><h3 dir={dir}>{t('גמר NBA','NBA Finals')}</h3>
            <PlayoffMatch match={bracket.finals}/>
            {bracket.champion?<p className="playoff-champion" dir={dir}>{t('האלופה','Champion')}<TeamLogo name={bracket.champion}/><strong dir="ltr">{teamBrand(bracket.champion)?.nickname??bracket.champion}</strong></p>:<p className="playoff-finals-note" dir={dir}>{t('ארבעה ניצחונות. אלופה אחת.','Four wins. One champion.')}</p>}
          </div></div>
        </section>;
        return <section className={'bracket-wing bracket-'+side} key={side} aria-labelledby={id+'-'+side}>
          <h2 id={id+'-'+side} dir={dir}><span>{side==='west'?'WESTERN':'EASTERN'}</span>{side==='west'?t('האזור המערבי','Western Conference'):t('האזור המזרחי','Eastern Conference')}</h2>
          <div className="bracket-wing-rounds">{rounds.map(round=><div className={'bracket-column bracket-'+round.key} key={round.key}>
            <h3 dir={dir}>{t(round.he,round.en)}</h3>
            <div className="bracket-pairs">{bracket[side][round.key].map((match,slot)=><PlayoffMatch key={slot} match={match}/>)}</div>
          </div>)}</div>
        </section>;
      })}
    </div>
  </div>;
}
