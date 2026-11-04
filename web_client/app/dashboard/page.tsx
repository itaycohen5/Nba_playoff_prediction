'use client';

import Link from 'next/link';
import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useLanguage } from '@/lib/i18n';
import { api, ApiError, record, parseUser, parseLines, parseFutures, money, wagerValue, messageOf, type Line, type User } from '@/lib/api';
import { useProtected } from '@/lib/use-protected';
import { Shell, LoadError, Notice, ConfirmDialog } from '@/components/ui';

async function loadDashboard(signal?: AbortSignal) {
  const [user, lines, futures] = await Promise.all([
    api('/me', parseUser, undefined, 15000, signal),
    api('/betting-lines', parseLines, undefined, 15000, signal),
    api('/futures-lines', parseFutures, undefined, 15000, signal),
  ]);
  return {user, lines, futures};
}
type Market = 'moneyline' | 'series_winner' | 'spread' | 'over_under_points';
type Conference = 'all' | 'west' | 'east' | 'finals';
type Selection = {type: Market | 'futures_champion'; target: string; value: number | null; odds: number};
type Place = (matchup: string, game: number, selection: Selection, amount: number) => Promise<void>;
type Simulate = (path: string, body: Record<string, unknown>, success?: string) => Promise<void>;

function SeriesStrip({nextGame}: {nextGame: number}) {
  const {t} = useLanguage();
  return <ol className="td-series-strip" aria-label={t('התקדמות סדרת הטוב משבעה','Best-of-seven series progress')}>
    {Array.from({length:7}, (_,i) => i+1).map(game => <li key={game} className={game < nextGame ? 'td-played' : game === nextGame ? 'td-next' : ''} aria-current={game === nextGame ? 'step' : undefined}>
      <span className="td-game-number">{game}</span><span>{game < nextGame ? t('שוחק','Played') : game === nextGame ? t('הבא','Next') : '—'}</span>
    </li>)}
  </ol>;
}

function GameCard({line,user,busy,place,simulate,featured}: {line:Line;user:User;busy:boolean;place:Place;simulate:Simulate;featured:boolean}) {
  const {t,locale} = useLanguage();
  const id = useId();
  const [market,setMarket] = useState<Market>('moneyline');
  const [selection,setSelection] = useState<Selection|null>(null);
  const [amount,setAmount] = useState('');
  const [error,setError] = useState('');
  const odds = line.odds;
  const tabs: {key:Market;label:string}[] = [
    {key:'moneyline',label:t('משחק','Game')},
    ...(odds?.series_winner ? [{key:'series_winner' as const,label:t('סדרה','Series')}] : []),
    ...(odds?.spread ? [{key:'spread' as const,label:t('הפרש','Spread')}] : []),
    {key:'over_under_points',label:t('נקודות','Total')},
  ];
  const options: {selection:Selection;label:string}[] = !odds ? [] : market === 'over_under_points' ? [
    {selection:{type:market,target:'Over',value:odds.over_under_points.line,odds:odds.over_under_points.over_odds},label:t('מעל','Over')},
    {selection:{type:market,target:'Under',value:odds.over_under_points.line,odds:odds.over_under_points.under_odds},label:t('מתחת','Under')},
  ] : [line.team1,line.team2].map((team,index) => {
    const spread = index === 0 ? odds.spread?.team1_spread : odds.spread?.team2_spread;
    return {selection:{type:market,target:team,value:market === 'spread' ? spread ?? null : null,
      odds:market === 'series_winner' ? odds.series_winner![team] : market === 'spread' ? odds.spread!.odds : odds.moneyline[team]},
      label:market === 'spread' ? `${team} (${(spread ?? 0) > 0 ? '+' : ''}${spread})` : team};
  });
  function chooseMarket(next:Market) {setMarket(next);setSelection(null);setError('');}
  function tabKeys(event:KeyboardEvent<HTMLButtonElement>, index:number) {
    const forward = locale === 'he' ? 'ArrowLeft' : 'ArrowRight';
    const backward = locale === 'he' ? 'ArrowRight' : 'ArrowLeft';
    let target = index;
    if (event.key === forward) target = (index+1)%tabs.length;
    else if (event.key === backward) target = (index-1+tabs.length)%tabs.length;
    else if (event.key === 'Home') target = 0;
    else if (event.key === 'End') target = tabs.length-1;
    else return;
    event.preventDefault();chooseMarket(tabs[target].key);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[target]?.focus();
  }
  async function submit(event:React.FormEvent) {
    event.preventDefault();if (busy) return;setError('');
    try {
      if (!selection) throw new Error('יש לבחור תחזית לפני השליחה');
      await place(line.series_id,line.next_game_number,selection,wagerValue(amount,user.balance));
      setAmount('');setSelection(null);
    } catch(e) {setError(messageOf(e));}
  }
  const scores = line.series_score.split('-').map(value => value.trim());
  const conference = line.series_id.startsWith('West') ? t('מערב','West') : line.series_id.startsWith('East') ? t('מזרח','East') : t('גמר NBA','NBA Finals');
  return <article className={`td-match ${featured ? 'td-featured' : ''}`} aria-labelledby={`${id}-title`}>
    <header className="td-match-meta"><span>{conference} · {t('משחק','Game')} {line.next_game_number}</span><span>{t('סדרה','Series')} <b dir="ltr">{line.series_score}</b></span></header>
    <h2 id={`${id}-title`} className="td-match-title"><span className="td-team-title-row"><span dir="auto">{line.team1}</span><b>{scores[0] ?? '—'}</b></span><span className="td-team-title-row"><span dir="auto">{line.team2}</span><b>{scores[1] ?? '—'}</b></span></h2>
    <SeriesStrip nextGame={line.next_game_number}/>
    {line.is_unlocked && odds ? <>
      <div className="td-market-tabs" role="tablist" aria-label={t('סוג שוק','Market type')}>
        {tabs.map((tab,index) => <button key={tab.key} type="button" role="tab" id={`${id}-tab-${tab.key}`} aria-selected={market === tab.key} aria-controls={`${id}-market`} tabIndex={market === tab.key ? 0 : -1} disabled={busy} onKeyDown={event => tabKeys(event,index)} onClick={() => chooseMarket(tab.key)}>{tab.label}</button>)}
      </div>
      <div id={`${id}-market`} role="tabpanel" aria-labelledby={`${id}-tab-${market}`} className="td-market-panel">
        <p className="td-market-label">{market === 'moneyline' ? t('מנצחת המשחק','Game winner') : market === 'series_winner' ? t('מנצחת הסדרה','Series winner') : market === 'spread' ? t('הפרש נקודות','Point spread') : t(`סך נקודות: ${odds.over_under_points.line}`,`Total points: ${odds.over_under_points.line}`)}</p>
        <div className="td-quote-row">{options.map(option => <button key={option.selection.target} type="button" className={`td-quote ${selection?.type === market && selection.target === option.selection.target ? 'td-selected' : ''}`} disabled={busy} aria-pressed={selection?.type === market && selection.target === option.selection.target} onClick={() => {setSelection(option.selection);setError('');}}><span dir="auto">{option.label}</span><strong dir="ltr">{option.selection.odds.toFixed(2)}</strong></button>)}</div>
      </div>
      <form onSubmit={submit} className="td-bet-form" aria-busy={busy}>
        {error && <Notice error>{error}</Notice>}
        <div className="td-bet-row"><label htmlFor={`${id}-amount`}>{t('סכום מדומה ($)','Virtual wager ($)')}<input id={`${id}-amount`} type="number" min="0.01" max={user.balance} step="0.01" inputMode="decimal" value={amount} onChange={event => setAmount(event.target.value)} placeholder="0.00" required disabled={busy}/></label><button className={`td-submit ${featured ? 'td-submit-lead' : ''}`} disabled={busy || user.balance <= 0}>{busy ? t('מתבצע…','Working…') : t('שליחת הימור','Place bet')}</button></div>
        <p className="td-return">{selection && amount && Number.isFinite(Number(amount)) ? <>{t('זכייה אפשרית','Potential return')} <strong dir="ltr">{money(Number(amount)*selection.odds)}</strong> <span>{t('כולל סכום ההימור','including stake')}</span></> : t('בחרו יחס כדי להרכיב הימור.','Select odds to build a bet.')}</p>
      </form>
      <footer className="td-match-actions"><button type="button" disabled={busy} onClick={() => void simulate('/simulate-game',{matchup:line.series_id,game_number:line.next_game_number}).catch(() => {})}>{t('הרצת משחק','Simulate game')}</button><button type="button" disabled={busy} onClick={() => void simulate('/simulate-series-auto',{matchup:line.series_id}).catch(() => {})}>{t('הרצת סדרה','Simulate series')}</button></footer>
    </> : <p className="td-no-market">{t('השוק ייפתח כאשר המשתתפות ייקבעו.','The market opens once the teams are confirmed.')}</p>}
  </article>;
}

function DashboardLoading() {
  const {t} = useLanguage();
  return <Shell><div className="td-dashboard"><header className="td-title-row"><h1>{t('שווקי הפלייאוף','Playoff markets')}</h1></header><div className="td-loading" role="status" aria-label={t('טוענים סדרות ויחסים','Loading series and odds')}><p>{t('טוענים סדרות ויחסים…','Loading series and odds…')}</p><div className="td-skeleton-row"><div/><div/></div></div></div></Shell>;
}

export default function Dashboard() {
  const {t} = useLanguage();
  const router = useRouter();
  const {data,error,loading,refresh} = useProtected(loadDashboard);
  const lock = useRef(false), lastAttempt = useRef<{fingerprint:string;requestId:string}|null>(null);
  const [busy,setBusy] = useState(false), [actionError,setActionError] = useState(''), [message,setMessage] = useState('');
  const [team,setTeam] = useState(''), [wager,setWager] = useState(''), [confirmReset,setConfirmReset] = useState(false);
  const [conference,setConference] = useState<Conference>('all');

  async function mutate(path:string,body:Record<string,unknown>,success?:string):Promise<void> {
    if (lock.current) throw new Error('פעולה אחרת עדיין מתבצעת');
    const fingerprint = JSON.stringify({path,body,tournament:data?.lines.tournament_id});
    const requestId = lastAttempt.current?.fingerprint === fingerprint ? lastAttempt.current.requestId : crypto.randomUUID();
    lastAttempt.current = {fingerprint,requestId};lock.current = true;setBusy(true);setActionError('');setMessage('');
    try {
      const result = await api(path,record,{...body,request_id:requestId},path === '/simulate-tournament-auto' ? 120000 : 30000);
      lastAttempt.current = null;
      const game = result.game_result && typeof result.game_result === 'object' ? record(result.game_result) : null;
      setMessage(game && typeof game.winner === 'string' ? `מנצחת המשחק: ${game.winner} · ${game.t1_pts}–${game.t2_pts}` : success ?? 'הסימולציה הושלמה. התוצאות עודכנו.');
      await refresh();
    } catch(e) {
      if (e instanceof ApiError && e.status > 0) lastAttempt.current = null;
      if (e instanceof ApiError && e.status === 401) router.replace('/login');
      if (e instanceof ApiError && e.status === 409) await refresh();
      setActionError(messageOf(e));throw e;
    } finally {lock.current = false;setBusy(false);}
  }
  const place:Place = async (matchup,game_number,selection,amount) => {
    await mutate('/place-bet',{matchup,game_number,bet_type:selection.type,team_bet_on:selection.target,target_value:selection.value,odds:selection.odds,amount},`התחזית נקלטה · זכייה אפשרית ${money(amount*selection.odds)}`);
  };
  async function futureSubmit(event:React.FormEvent) {
    event.preventDefault();if (!data || busy) return;
    try {
      const selected = data.futures.find(future => future.team === team);
      if (!selected) throw new Error('יש לבחור קבוצה');
      await place('NBA Finals',0,{type:'futures_champion',target:team,value:null,odds:selected.odds},wagerValue(wager,data.user.balance));
      setTeam('');setWager('');
    } catch(e) {setActionError(messageOf(e));}
  }
  if (loading) return <DashboardLoading/>;
  if (!data) return <Shell><div className="td-dashboard"><LoadError message={error} retry={() => void refresh()}/></div></Shell>;

  const {user,lines,futures} = data;
  const groups:{key:Conference;label:string;items:Line[]}[] = [
    {key:'all',label:t('הכול','All'),items:lines.betting_lines},
    {key:'west',label:t('מערב','West'),items:lines.betting_lines.filter(line => line.series_id.startsWith('West'))},
    {key:'east',label:t('מזרח','East'),items:lines.betting_lines.filter(line => line.series_id.startsWith('East'))},
    {key:'finals',label:t('גמר','Finals'),items:lines.betting_lines.filter(line => line.series_id === 'NBA Finals')},
  ];
  const visible = groups.find(group => group.key === conference)!.items;
  const rounds = [t('סיבוב ראשון','First round'),t('חצי גמר אזורי','Conference semifinals'),t('גמר אזורי','Conference finals'),t('גמר NBA','NBA Finals')];
  const round = lines.champion ? t('הטורניר הושלם','Tournament complete') : rounds[lines.active_round-1] ?? t('פלייאוף','Playoffs');
  const selectedFuture = futures.find(future => future.team === team);
  return <Shell user={user}><div className="td-dashboard">
    <header className="td-title-row"><div><h1>{t('שווקי הפלייאוף','Playoff markets')}</h1><p>{round}<span>·</span>{t('עונה','Season')} #{lines.tournament_id}<span>·</span>{lines.betting_lines.length} {t('סדרות פתוחות','open series')}</p></div><button type="button" className="button ghost" disabled={busy} onClick={() => void refresh()}>{t('רענון יחסים','Refresh odds')}</button></header>
    {error && <Notice error>{error}</Notice>}{actionError && <Notice error>{actionError}</Notice>}{message && <Notice>{message}</Notice>}
    <div className="td-workspace">
      <section className="td-markets" aria-label={t('משחקים זמינים להימור','Available games to bet')}>
        <div className="td-conference-filters" role="group" aria-label={t('סינון לפי אזור','Filter by conference')}>{groups.map(group => <button type="button" key={group.key} aria-pressed={conference === group.key} className={conference === group.key ? 'td-active-filter' : ''} onClick={() => setConference(group.key)}>{group.label}<span>{group.items.length}</span></button>)}</div>
        {visible.length ? <div className="td-match-grid">{visible.map((line,index) => <GameCard key={`${lines.tournament_id}:${line.series_id}:${line.next_game_number}`} line={line} user={user} busy={busy} place={place} simulate={mutate} featured={index === 0}/>)}</div> : <div className="td-market-empty"><h2>{lines.champion ? t('האלופה נקבעה','The champion is decided') : t('אין סדרות פתוחות באזור הזה','No open series in this conference')}</h2><p>{lines.champion ?? t('סדרות חדשות נפתחות כשהסיבוב הקודם מסתיים.','New series open when the previous round ends.')}</p>{conference !== 'all' && <button className="button ghost" onClick={() => setConference('all')}>{t('כל הסדרות','All series')}</button>}{lines.champion && <Link className="text-link" href="/bracket">{t('תוצאות הטורניר','Tournament results')}</Link>}</div>}
      </section>
      <aside className="td-rail" aria-label={t('אליפות וניהול טורניר','Championship and tournament controls')}>
        <section className="td-side-panel"><h2>{t('אלופת NBA','NBA champion')}</h2>{lines.champion ? <div className="td-champion"><p>{t('האלופה בעונה הזאת','This season’s champion')}</p><strong dir="auto">{lines.champion}</strong><Link className="text-link" href="/history">{t('לבדיקת ההימורים','Review your bets')}</Link></div> : <form onSubmit={futureSubmit} className="td-future-form" aria-busy={busy}><label htmlFor="td-future-team">{t('קבוצה לאליפות','Championship pick')}<select id="td-future-team" value={team} onChange={event => setTeam(event.target.value)} disabled={busy} required><option value="">{t('בחירת קבוצה','Select a team')}</option>{futures.map(future => <option key={future.team} value={future.team}>{future.team} · {future.odds.toFixed(2)}</option>)}</select></label><div className="td-bet-row"><label htmlFor="td-future-amount">{t('סכום מדומה ($)','Virtual wager ($)')}<input id="td-future-amount" type="number" min="0.01" max={user.balance} step="0.01" inputMode="decimal" value={wager} onChange={event => setWager(event.target.value)} placeholder="0.00" disabled={busy} required/></label><button className="td-submit" disabled={busy || user.balance <= 0}>{t('שליחת הימור','Place bet')}</button></div><p className="td-return">{selectedFuture ? <>{t('יחס נבחר','Selected odds')} <strong dir="ltr">{selectedFuture.odds.toFixed(2)}</strong></> : t('שוק האליפות נסגר בהכרעת הטורניר.','The championship market closes when the tournament is decided.')}</p></form>}</section>
        <section className="td-side-panel td-tournament-controls"><h2>{t('הרצת הטורניר','Tournament simulation')}</h2><p>{t('משחקים בודדים משאירים את ההחלטה הבאה בידיים שלך. הרצה מלאה מכריעה את כל הסדרות.','Individual games leave the next decision to you. A full simulation settles every series.')}</p><button className="button ghost" disabled={busy || !!lines.champion} onClick={() => void mutate('/simulate-tournament-auto',{}).catch(() => {})}>{busy ? t('מריצים…','Simulating…') : t('הרצת כל הפלייאוף','Simulate playoffs')}</button></section>
        <section className="td-side-panel td-season-controls"><h2>{t('העונה והיתרה','Season and balance')}</h2><button type="button" disabled={busy || user.balance > 1} onClick={() => void mutate('/reload-bank',{},'נוספו $1,000 מדומים ליתרה').catch(() => {})}>{t('קבלת $1,000 מדומים','Claim $1,000 virtual funds')}</button><small>{t('זמין ביתרה של $1 או פחות, בכפוף לזמן המתנה.','Available at a balance of $1 or less, subject to a waiting period.')}</small><button type="button" disabled={busy} onClick={() => setConfirmReset(true)}>{t('פתיחת עונה חדשה','Start new season')}</button><small>{t('הימורים פתוחים יוחזרו. ההיסטוריה נשמרת.','Open bets will be refunded. Your history is preserved.')}</small></section>
        <p className="td-data-note">{t('כסף מדומה בלבד. נתונים היסטוריים שנשמרו בפרויקט; אין תוצאות חיות או דירוג רשמי.','Virtual funds only. Historical project data, not live results or official standings.')}{lines.data_source.toLowerCase().includes('fallback') && <> {t('כרגע מופעלים נתוני גיבוי מדומים.','Simulated fallback data is currently in use.')}</>}</p>
      </aside>
    </div>
    {confirmReset && <ConfirmDialog busy={busy} cancel={() => setConfirmReset(false)} confirm={() => void mutate('/reset-tournament',{},'העונה החדשה מוכנה. בהצלחה!').then(() => setConfirmReset(false)).catch(() => {})}/>}
  </div></Shell>;
}
