export class ApiError extends Error {
  constructor(message: string, public status = 0) { super(message); }
}
type Parser<T> = (value: unknown) => T;
export const record = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError('השרת החזיר נתונים לא תקינים');
  return value as Record<string, unknown>;
};
export const text = (value: unknown): string => {
  if (typeof value !== 'string') throw new ApiError('שדה טקסט חסר בתשובת השרת');
  return value;
};
export const number = (value: unknown): number => {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new ApiError('נתון מספרי לא תקין');
  return value;
};
const list = <T>(value: unknown, parse: Parser<T>): T[] => {
  if (!Array.isArray(value)) throw new ApiError('רשימת נתונים לא תקינה');
  return value.map(parse);
};
export interface User { user_id: number; username: string; balance: number }
export function parseUser(value: unknown): User {
  const r = record(value);
  return { user_id: number(r.user_id), username: text(r.username), balance: number(r.balance) };
}
export interface Odds { moneyline: Record<string, number>; series_winner?: Record<string, number>; spread?: {team1_spread: number; team2_spread: number; odds: number}; over_under_points: {line: number; over_odds: number; under_odds: number} }
export interface Line { series_id: string; team1: string; team2: string; home_team: string | null; series_score: string; next_game_number: number; is_unlocked: boolean; odds: Odds | null }
function numericRecord(value: unknown): Record<string, number> {
  return Object.fromEntries(Object.entries(record(value)).map(([k,v]) => [k, number(v)]));
}
function parseLine(value: unknown): Line {
  const r = record(value);
  if (typeof r.is_unlocked !== 'boolean') throw new ApiError('מצב סדרה לא תקין');
  let odds: Odds | null = null;
  if (r.odds !== null) {
    const o = record(r.odds), total = record(o.over_under_points);
    odds = { moneyline: numericRecord(o.moneyline), series_winner: o.series_winner ? numericRecord(o.series_winner) : undefined,
      over_under_points: {line: number(total.line), over_odds: number(total.over_odds), under_odds: number(total.under_odds)} };
    if (o.spread) {const spread = record(o.spread); odds.spread = {team1_spread: number(spread.team1_spread), team2_spread: number(spread.team2_spread), odds: number(spread.odds)};}
  }
  const line = { series_id: text(r.series_id), team1: text(r.team1), team2: text(r.team2), home_team: r.home_team == null ? null : text(r.home_team), series_score: text(r.series_score), next_game_number: number(r.next_game_number), is_unlocked: r.is_unlocked, odds };
  if (odds && (!Number.isFinite(odds.moneyline[line.team1]) || !Number.isFinite(odds.moneyline[line.team2]))) throw new ApiError('יחסי המשחק אינם תקינים');
  if (odds?.series_winner && (!Number.isFinite(odds.series_winner[line.team1]) || !Number.isFinite(odds.series_winner[line.team2]))) throw new ApiError('יחסי הסדרה אינם תקינים');
  return line;
}
export interface Lines { active_round: number; betting_lines: Line[]; tournament_id: number; champion: string | null; data_source: string }
export function parseLines(value: unknown): Lines {
  const r = record(value);
  return { active_round: number(r.active_round), betting_lines: list(r.betting_lines, parseLine), tournament_id: number(r.tournament_id), champion: r.champion == null ? null : text(r.champion), data_source: text(r.data_source) };
}
export interface Future { team: string; odds: number }
export function parseFutures(value: unknown): Future[] {
  return list(record(value).futures_lines, value => { const r = record(value); return {team: text(r.team), odds: number(r.odds)}; });
}
export interface HistoryBet { id: number; matchup: string; game_number: number; bet_type: string; team_bet_on: string; amount: number; odds: number; status: string; tournament_id: number; created_at: string; potential_win: number; paid_out: number }
export function parseHistory(value: unknown): HistoryBet[] {
  return list(record(value).history, value => { const r = record(value); return {id: number(r.id), matchup: text(r.matchup), game_number: number(r.game_number), bet_type: text(r.bet_type), team_bet_on: text(r.team_bet_on), amount: number(r.amount), odds: number(r.odds), status: text(r.status), tournament_id: number(r.tournament_id), created_at: text(r.created_at), potential_win: number(r.potential_win), paid_out: number(r.paid_out)}; });
}
export interface Team { name: string; wins: number }
export interface Matchup { t1: Team; t2: Team }
export interface Conference { r1: Matchup[]; r2: Matchup[]; r3: Matchup[] }
export interface Bracket { west: Conference; east: Conference; finals: Matchup; champion: string | null }
function parseMatch(value: unknown): Matchup {
  const r = record(value);
  const team = (value: unknown): Team => { const r = record(value); return {name: r.name == null ? 'TBD' : text(r.name), wins: number(r.wins)}; };
  return { t1: team(r.t1), t2: team(r.t2) };
}
export function parseBracket(value: unknown): Bracket {
  const r = record(value);
  const conference = (value: unknown): Conference => { const r = record(value); return {r1: list(r.r1, parseMatch), r2: list(r.r2, parseMatch), r3: list(r.r3, parseMatch)}; };
  return {west: conference(r.west), east: conference(r.east), finals: parseMatch(r.finals), champion: r.champion == null ? null : text(r.champion)};
}
export async function api<T>(path: string, parse: Parser<T>, body?: unknown, timeout = 15000, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: body === undefined ? undefined : {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body), signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(timeout)]) : AbortSignal.timeout(timeout) });
  } catch (error) {
    if (signal?.aborted) throw error;
    if (path === '/login' || path === '/register') {
      throw new ApiError('לא התקבלה תשובה משירות הכניסה. בדקו את החיבור ונסו שוב.');
    }
    throw new ApiError('לא התקבלה תשובה מהשרת. בפעולת הימור אפשר לנסות שוב עם אותם פרטים ללא חיוב כפול.');
  }
  const value: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = value && typeof value === 'object' && 'detail' in value ? value.detail : null;
    if ((path === '/login' || path === '/register') && response.status >= 500) {
      throw new ApiError('שירות הכניסה אינו זמין כרגע. נסו שוב בעוד רגע.', response.status);
    }
    const message = response.status >= 500 ? 'השירות אינו זמין כרגע. נסו שוב בעוד רגע.' : Array.isArray(detail) ? detail.map(v => v && typeof v === 'object' && 'msg' in v ? String(v.msg) : 'קלט לא תקין').join(' · ') : typeof detail === 'string' ? detail : 'הפעולה לא הושלמה. יש לבדוק את הפרטים ולנסות שוב.';
    throw new ApiError(response.status === 401 && path !== '/login' ? 'יש להתחבר מחדש' : message, response.status);
  }
  return parse(value);
}
export const money = (value: number) => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', maximumFractionDigits: 2}).format(value);
export function wagerValue(raw: string, balance: number): number {
  const amount = Number(raw), cents = Math.round(amount * 100);
  if (!raw.trim() || !Number.isFinite(amount) || cents < 1 || Math.abs(amount * 100 - cents) > 1e-7 || amount > balance) throw new ApiError('יש להזין סכום חיובי, עד שתי ספרות אחרי הנקודה ובמסגרת היתרה');
  return cents / 100;
}
export const messageOf = (error: unknown) => error instanceof Error ? error.message : 'הפעולה נכשלה';

const messageTranslations: Record<string, string> = {
  "השרת החזיר נתונים לא תקינים": "The server returned invalid data",
  "שדה טקסט חסר בתשובת השרת": "A text field is missing from the response",
  "נתון מספרי לא תקין": "Invalid numeric data",
  "רשימת נתונים לא תקינה": "Invalid data list",
  "מצב סדרה לא תקין": "Invalid series state",
  "יחסי המשחק אינם תקינים": "Invalid game odds",
  "יחסי הסדרה אינם תקינים": "Invalid series odds",
  "לא התקבלה תשובה מהשרת. בפעולת הימור אפשר לנסות שוב עם אותם פרטים ללא חיוב כפול.": "The server did not respond. You can retry the same bet without being charged twice.",
  "לא התקבלה תשובה משירות הכניסה. בדקו את החיבור ונסו שוב.": "The sign-in service did not respond. Check your connection and try again.",
  "שירות הכניסה אינו זמין כרגע. נסו שוב בעוד רגע.": "The sign-in service is temporarily unavailable. Try again shortly.",
  "השירות אינו זמין כרגע. נסו שוב בעוד רגע.": "The service is temporarily unavailable. Please try again shortly.",
  "הפעולה לא הושלמה. יש לבדוק את הפרטים ולנסות שוב.": "The action could not be completed. Check your details and try again.",
  "יש להתחבר מחדש": "Please sign in again",
  "יש להזין סכום חיובי, עד שתי ספרות אחרי הנקודה ובמסגרת היתרה": "Enter a positive amount within your balance, with up to two decimal places",
  "הפעולה נכשלה": "The action failed",
  "קלט לא תקין": "Invalid input",
  "יש לבחור תחזית לפני השליחה": "Select a prediction before submitting",
  "פעולה אחרת עדיין מתבצעת": "Another action is still in progress",
  "הסימולציה הושלמה. התוצאות עודכנו.": "Simulation complete. The results have been updated.",
  "יש לבחור קבוצה": "Please select a team",
  "נוספו $1,000 מדומים ליתרה": "$1,000 in virtual funds has been added to your balance",
  "העונה החדשה מוכנה. בהצלחה!": "Your new season is ready. Good luck!",
  "שם משתמש: 3–40 אותיות, ספרות או קו תחתון, ללא רווחים": "Username: 3–40 letters, numbers or underscores, without spaces",
  "נדרשת סיסמה עם לפחות 8 תווים ועד 72 בתים (תווים בעברית תופסים יותר מבית אחד)": "Use at least 8 characters and up to 72 UTF-8 bytes (some characters use more than one byte)",
  "יש להזין סיסמה באורך עד 72 בתים": "Enter a password of up to 72 UTF-8 bytes",
  "הסיסמאות אינן תואמות": "The passwords do not match",
  "יש להזין שם משתמש": "Please enter a username",
  "סיסמה מוגבלת ל־72 בתים בקידוד UTF-8": "Passwords are limited to 72 UTF-8 bytes",
  "שם משתמש: 3–40 אותיות, ספרות או קו תחתון": "Username: 3–40 letters, numbers or underscores",
  "המשתמש אינו זמין": "This account is unavailable",
  "לא ניתן לבצע פעולה בשם משתמש אחר": "You cannot act on behalf of another user",
  "מזהה הבקשה כבר שימש לפעולה אחרת": "This request has already been used for a different action",
  "הסדרה אינה פעילה": "This series is not active",
  "הקבוצות אינן תואמות לסדרה": "The teams do not match this series",
  "הסדרה כבר הסתיימה": "This series has already ended",
  "היסטוריית הסדרה אינה תקינה": "The series history is invalid",
  "הימור אליפות דורש שוק אליפות ומספר משחק 0": "The championship bet does not match the market",
  "שוק האליפות סגור או שהקבוצה הודחה": "The championship market is closed or the team has been eliminated",
  "ניתן להמר רק על המשחק הבא שטרם שוחק": "You can only bet on the next unplayed game",
  "יש לבחור קבוצה שמשתתפת בסדרה": "Select a team participating in this series",
  "קבוצה לא תקינה": "Invalid team",
  "יש לבחור מעל או מתחת לקו": "Select over or under the total",
  "מספר המשחק השתנה. רעננו את הנתונים": "The game number has changed. Refresh the data",
  "העונה השתנתה. רעננו את הנתונים לפני הפעולה": "The season has changed. Refresh the data before trying again",
  "שם המשתמש כבר קיים": "This username is already taken",
  "יותר מדי ניסיונות. נסו שוב בעוד 15 דקות": "Too many attempts. Please try again in 15 minutes",
  "שם המשתמש או הסיסמה שגויים": "The username or password is incorrect",
  "אין הרשאה למשתמש זה": "You do not have permission to access this account",
  "יחס ההימור או הקו השתנו. בחרו הצעה מעודכנת": "The odds or line have changed. Choose an updated offer",
  "אין מספיק יתרה מדומה": "Insufficient virtual balance",
  "הסדרה לא הגיעה להכרעה תקינה": "The series could not be completed correctly",
  "הטורניר אינו יכול להתקדם": "The tournament cannot advance",
  "הטורניר לא הושלם": "The tournament has not been completed",
  "מילוי יתרה זמין ביתרה של דולר מדומה אחד או פחות": "Virtual funds are available when your balance is $1 or less",
  "יש להמתין 10 שניות בין מילויים": "Please wait 10 seconds between balance top-ups"
};
export function translateMessage(message: string, locale: 'he' | 'en'): string {
  if (locale === 'he') return message;
  if (messageTranslations[message]) return messageTranslations[message];
  if (message.startsWith('מנצחת המשחק: ')) return message.replace('מנצחת המשחק: ', 'Game winner: ');
  if (message.startsWith('התחזית נקלטה · זכייה אפשרית ')) return message.replace('התחזית נקלטה · זכייה אפשרית ', 'Bet placed · Potential return ');
  if (message.includes(' · ')) return message.split(' · ').map(part => translateMessage(part, locale)).join(' · ');
  if (message.startsWith('Value error, ')) return translateMessage(message.slice(13), locale);
  if (/[\u0590-\u05ff]/.test(message)) return 'The action could not be completed. Check the details and try again.';
  return message;
}
