'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useLanguage } from '@/lib/i18n';
import { type Bracket } from '@/lib/api';
import opening from '@/lib/demo-bracket.json';
import market from '@/lib/demo-market.json';
import { PlayoffBracket,PlayoffMatch } from './playoff-bracket';
import { TeamLogo,teamBrand } from './team-logo';

export function ProductPreview({view}:{view:string}){
  const {t}=useLanguage(),[kind,setKind]=useState<'moneyline'|'series_winner'>('moneyline'),[pick,setPick]=useState('');
  const bracket=opening as Bracket;
  return <div className="product-preview" data-ui>
    <header className="preview-toolbar"><span className="preview-brand">PLAYOFF LAB <b>{t('תצוגת הדגמה','DEMO VIEW')}</b></span><span>{t('נתוני פתיחת עונה · יתרה מדומה','Opening season · Virtual funds')}</span></header>
    {view==='bracket'?<><p className="preview-scroll-note">{t('מערב משמאל, מזרח מימין. גללו לצדדים כדי לעקוב אחר כל הדרך לגמר.','West on the left, East on the right. Scroll horizontally to follow the road to the Finals.')}</p><PlayoffBracket bracket={bracket} preview/></>:view==='court'?<div className="preview-court">
      <div className="preview-heading"><div><p>{t('סיבוב ראשון','FIRST ROUND')}</p><h3>{t('המגרש מוכן. הבחירה שלך.','The court is set. Your call.')}</h3></div><span>{t('8 סדרות · הטוב מ־7','8 series · Best of seven')}</span></div>
      <div className="preview-match-grid">{[...bracket.west.r1,...bracket.east.r1].map((match,index)=><section key={index}><h4>{index<4?t('מערב','WEST'):t('מזרח','EAST')}</h4><PlayoffMatch match={match}/></section>)}</div>
      <Link className="button primary" href="/register">{t('פתיחת טורניר אישי','Start a personal tournament')} ↗</Link>
    </div>:view==='markets'?<div className="preview-markets">
      <section className="preview-market-teams">{[market.team1,market.team2].map(name=><div key={name}><TeamLogo name={name}/><small>{teamBrand(name)?.city}</small><h3>{teamBrand(name)?.nickname}</h3></div>)}</section>
      <section className="preview-market-panel"><p>{t('הדגמת שוק · נתוני מודל שמורים','MARKET DEMO · SAVED MODEL DATA')}</p><h3>{t('קוראים את המשחק. בוחרים צד.','Read the game. Pick your side.')}</h3>
        <div className="preview-market-tabs" role="group" aria-label={t('בחירת שוק להדגמה','Choose a demo market')}>{(['moneyline','series_winner'] as const).map(value=><button key={value} aria-pressed={kind===value} onClick={()=>{setKind(value);setPick('');}}>{value==='moneyline'?t('מנצחת המשחק','Game winner'):t('מנצחת הסדרה','Series winner')}</button>)}</div>
        <div className="preview-quotes">{[market.team1,market.team2].map(name=><button key={name} aria-pressed={pick===name} onClick={()=>setPick(name)}><TeamLogo name={name}/><span>{teamBrand(name)?.nickname}</span><strong>{(market.odds[kind] as Record<string,number>)[name].toFixed(2)}</strong></button>)}</div>
        <p role="status">{pick?t('נבחרה תחזית להדגמה בלבד. לא נשלח הימור.','Demo selection only. No wager was placed.'):t('בחרו יחס כדי לנסות את התצוגה.','Select a price to try the preview.')}</p><Link className="text-link" href="/register">{t('לכל השווקים בטורניר אישי','Explore all markets in your tournament')} ↗</Link>
      </section>
    </div>:<div className="preview-ledger">
      <div className="preview-heading"><div><p>{t('ההיסטוריה שלך','YOUR RECORD')}</p><h3>{t('כל בחירה נשארת על הלוח.','Every pick stays on the record.')}</h3></div><span>{t('תצוגת חשבון חדש','New-account preview')}</span></div>
      <div className="preview-ledger-head"><span>{t('תחזית','Prediction')}</span><span>{t('סכום מדומה','Virtual stake')}</span><span>{t('יחס','Odds')}</span><span>{t('תוצאה','Result')}</span></div>
      <div className="preview-empty"><h4>{t('התחזית הראשונה שלך מתחילה במגרש.','Your first prediction starts on the court.')}</h4><p>{t('הבחירה, הסכום והתוצאה יופיעו כאן אחרי שליחת התחזית. אין נתוני משתמש אמיתיים בתצוגה הזו.','Your selection, stake and result appear here after you place a prediction. This preview contains no real user records.')}</p><Link className="button primary" href="/register">{t('יצירת החשבון שלך','Create your account')} ↗</Link></div>
    </div>}
  </div>;
}
