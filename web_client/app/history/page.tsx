'use client';
import Link from 'next/link';
import { api, parseUser, parseHistory, money } from '@/lib/api';
import { useProtected } from '@/lib/use-protected';
import { Shell, Loading, LoadError, Notice } from '@/components/ui';
import { useLanguage } from '@/lib/i18n';

async function load(signal?: AbortSignal) {
  const [user,history] = await Promise.all([api('/me',parseUser,undefined,15000,signal),api('/me/history',parseHistory,undefined,15000,signal)]);
  return {user,history};
}

export default function History() {
  const {t} = useLanguage();
  const {data,error,loading,refresh} = useProtected(load);
  if (loading) return <Shell><Loading/></Shell>;
  if (!data) return <Shell><LoadError message={error} retry={() => void refresh()}/></Shell>;
  const {user,history} = data;
  const statuses: Record<string,string> = {pending:t('פתוח','Pending'),won:t('זכייה','Won'),lost:t('הפסד','Lost'),push:t('החזר','Refunded'),cancelled:t('בוטל','Cancelled')};
  const types: Record<string,string> = {spread:t('הפרש נקודות','Point spread'),moneyline:t('מנצחת משחק','Game winner'),series_winner:t('מנצחת סדרה','Series winner'),over_under_points:t('סך נקודות','Total points'),futures_champion:t('אלופת NBA','NBA champion')};
  const amount = history.reduce((sum,bet) => sum + Math.round(bet.amount * 100),0) / 100;
  const paid = history.reduce((sum,bet) => sum + Math.round(bet.paid_out * 100),0) / 100;
  const pending = history.filter(bet => bet.status === 'pending').length;
  const headers = [t('תחזית','Prediction'),t('תאריך','Date'),t('סכום מדומה','Virtual wager'),t('יחס','Odds'),t('החזר','Return'),t('הכרעה','Result')];
  return <Shell user={user}>
    <header className="app-title-row"><div><h1>{t('ההימורים שלי','My bets')}</h1><p>{t(`${history.length} תחזיות מכל העונות · ${pending} ממתינות להכרעה`,`${history.length} predictions across all seasons · ${pending} awaiting results`)}</p></div><Link className="button ghost" href="/dashboard">{t('תחזית חדשה','New prediction')}</Link></header>
    {error && <Notice error>{error}</Notice>}
    <dl className="ledger-summary" aria-label={t('סיכום סכומים מדומים','Virtual funds summary')}>
      <div><dt>{t('סכום תחזיות כולל','Total wagered')}</dt><dd dir="ltr">{money(amount)}</dd></div>
      <div><dt>{t('הוחזר ליתרה','Returned to balance')}</dt><dd dir="ltr">{money(paid)}</dd></div>
      <div className="ledger-summary-note"><dt>{t('כסף מדומה בלבד','Virtual funds only')}</dt><dd>{t('החזרים כוללים זכיות, ביטולים והימורים שהוחזרו.','Returns include winnings, cancellations and refunded wagers.')}</dd></div>
    </dl>
    {!history.length ? <section className="app-empty ledger-empty"><h2>{t('עוד אין תחזיות בהיסטוריה','No predictions yet')}</h2><p>{t('התחזית הראשונה שתשלח תופיע כאן, יחד עם היחס והתוצאה.','Your first prediction will appear here with its odds and result.')}</p><Link className="text-link" href="/dashboard">{t('בחירת משחק ושליחת תחזית','Choose a game and make a prediction')}</Link></section> :
      <div className="ledger-frame"><table className="ledger-table">
        <caption className="visually-hidden">{t('כל ההימורים, הסכומים המדומים ותוצאות הסליקה','All bets, virtual wagers and settlement results')}</caption>
        <thead><tr>{headers.map((heading,index) => <th scope="col" className={index >= 2 && index <= 4 ? 'ledger-number' : ''} key={heading}>{heading}</th>)}</tr></thead>
        <tbody>{history.map(bet => {
          const date = new Date(bet.created_at);
          const validDate = !Number.isNaN(date.getTime());
          const selection = bet.team_bet_on === 'Over' ? t('מעל סך הנקודות','Over the total') : bet.team_bet_on === 'Under' ? t('מתחת לסך הנקודות','Under the total') : bet.team_bet_on;
          return <tr key={bet.id}>
            <th scope="row" className="ledger-pick"><span dir="auto">{selection}</span><small>{types[bet.bet_type] ?? bet.bet_type} · {t('עונה','Season')} #{bet.tournament_id}</small><small><bdi>{bet.matchup}</bdi>{bet.game_number > 0 ? t(` · משחק ${bet.game_number}`,` · Game ${bet.game_number}`) : ''}</small></th>
            <td className="ledger-date" data-label={headers[1]}>{validDate ? <time dateTime={bet.created_at}><span dir="ltr">{date.toISOString().slice(0,10)}</span></time> : <span>{t('תאריך לא זמין','Date unavailable')}</span>}</td>
            <td className="ledger-number" data-label={headers[2]}><bdi>{money(bet.amount)}</bdi></td>
            <td className="ledger-number" data-label={headers[3]}><bdi>{bet.odds.toFixed(2)}</bdi></td>
            <td className="ledger-number ledger-return" data-label={headers[4]}><bdi>{money(bet.status === 'pending' ? bet.potential_win : bet.paid_out)}</bdi><small>{bet.status === 'pending' ? t('אפשרי','Potential') : t('שולם','Paid')}</small></td>
            <td className="ledger-result" data-label={headers[5]}><span className={`status status-${bet.status}`}>{statuses[bet.status] ?? bet.status}</span></td>
          </tr>;
        })}</tbody>
      </table></div>}
  </Shell>;
}
