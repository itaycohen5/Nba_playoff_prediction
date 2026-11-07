"""Authenticated, transaction-safe personal NBA simulation API."""
import hashlib
import json
import logging
import math
import os
import re
import secrets
import string
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.db.auth import get_password_hash, verify_password
from backend.db.database import get_db, initialize_database
from backend.db.models import AccountEmail, AuthSession, Bet, GameHistory, LoginAttempt, Mutation, Tournament, User, utcnow
from backend.db.recovery import recovery_key, issue_recovery_code
from backend import email_delivery
from backend.playoff_engine import PlayoffEngine, odds_for_probability

logger = logging.getLogger(__name__)
engine_nba = PlayoffEngine()
COOKIE = 'nba_session'
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'true' if os.getenv('VERCEL') else 'false').lower() == 'true'
ORIGINS = [s.strip().rstrip('/') for s in os.getenv('APP_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if s.strip()]

@asynccontextmanager
async def lifespan(_app):
    initialize_database()
    yield

app = FastAPI(title='Playoff Predict — סימולטור אישי', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True,
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

@app.middleware('http')
async def origin_guard(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if (origin and origin.rstrip('/') not in ORIGINS) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'מקור הבקשה אינו מורשה'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.exception_handler(OperationalError)
async def database_busy(_request, _error):
    return JSONResponse({'detail': 'מסד הנתונים עסוק או אינו זמין. נסו שוב באותה בקשה.'}, status_code=503,
                        headers={'Retry-After': '2'})

@app.exception_handler(IntegrityError)
async def constraint_conflict(_request, _error):
    return JSONResponse({'detail': 'המצב השתנה. רעננו ונסו שוב.'}, status_code=409)

@app.exception_handler(email_delivery.DeliveryError)
async def email_unavailable(_request, _error):
    return JSONResponse({'detail': 'שליחת המייל אינה זמינה כרגע. נסו שוב מאוחר יותר.'}, status_code=503)

@app.exception_handler(RequestValidationError)
async def validation_error(_request, error):
    # Echoing raw input can disclose passwords or make invalid numbers fail JSON encoding.
    details = [{key: issue[key] for key in ('loc', 'msg', 'type')} for issue in error.errors()]
    return JSONResponse({'detail': details}, status_code=422)

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class EmailRequest(StrictModel):
    email: str = Field(max_length=254)
    _email = field_validator('email')(email_delivery.normalize_email)

class BindEmailRequest(EmailRequest):
    password: str = Field(min_length=1, max_length=72)

class VerifyEmailRequest(StrictModel):
    code: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')

class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=72)
    @field_validator('username')
    @classmethod
    def trim_username(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('יש להזין שם משתמש')
        return value
    @field_validator('password')
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('סיסמה מוגבלת ל־72 בתים בקידוד UTF-8')
        return value

def validate_new_password(value):
    missing = []
    if len(value) < 8:
        missing.append('לפחות 8 תווים')
    if not any(char in string.ascii_letters for char in value):
        missing.append('לפחות אות אחת באנגלית')
    if not any(char in string.digits for char in value):
        missing.append('לפחות ספרה אחת')
    if not any(char in string.punctuation for char in value):
        missing.append('לפחות תו מיוחד אחד')
    if missing:
        raise ValueError('דרישות סיסמה חסרות: ' + ', '.join(missing))
    return LoginRequest.password_bytes(value)


class RegisterRequest(LoginRequest):
    username: str = Field(min_length=3, max_length=40)
    password: str
    email: str | None = Field(default=None, max_length=254)
    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        return email_delivery.normalize_email(value) if value is not None else None
    _new_password = field_validator('password')(validate_new_password)
    @field_validator('username')
    @classmethod
    def valid_username(cls, value):
        if len(value) < 3 or not re.fullmatch(r'\w+', value, re.UNICODE):
            raise ValueError('שם משתמש: 3–40 אותיות, ספרות או קו תחתון')
        return value

class PasswordResetRequest(StrictModel):
    code: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    password: str
    _new_password = field_validator('password')(validate_new_password)

class ActionRequest(StrictModel):
    request_id: UUID = Field(default_factory=uuid4)
    user_id: int | None = None
    tournament_id: int | None = Field(default=None, gt=0, strict=True)

class PlaceBetRequest(ActionRequest):
    matchup: str = Field(min_length=1, max_length=80)
    game_number: int = Field(ge=0, le=7, strict=True)
    bet_type: Literal['moneyline', 'spread', 'over_under_points', 'series_winner', 'futures_champion']
    team_bet_on: str = Field(min_length=1, max_length=80)
    target_value: float | None = None
    amount: Decimal = Field(gt=0, le=Decimal('1000000000'), max_digits=12, decimal_places=2)
    odds: float | None = Field(default=None, ge=1, le=1000000)

class SeriesRequest(ActionRequest):
    matchup: str = Field(min_length=1, max_length=80)
    team1: str | None = None
    team2: str | None = None
    game_number: int | None = Field(default=None, ge=1, le=7, strict=True)

class GameRequest(SeriesRequest):
    game_number: int = Field(ge=1, le=7, strict=True)

# Compatibility names are imports only; identity is always the session owner.
SimulateGameRequest = GameRequest
SimulateSeriesAutoRequest = SeriesRequest
ReloadBankRequest = ActionRequest


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    token_hash = hashlib.sha256(token.encode()).hexdigest() if token else None
    auth = db.get(AuthSession, token_hash) if token_hash else None
    if auth is None or auth.expires_at <= utcnow():
        raise HTTPException(401, 'יש להתחבר מחדש')
    user = db.query(User).filter(User.id == auth.user_id).with_for_update().first()
    if user is None:
        raise HTTPException(401, 'המשתמש אינו זמין')
    # Logout uses the same user lock. Recheck after waiting for it.
    auth = db.get(AuthSession, token_hash, populate_existing=True)
    if auth is None or auth.expires_at <= utcnow():
        raise HTTPException(401, 'יש להתחבר מחדש')
    return user


def wallet(user):
    return {'id': user.id, 'user_id': user.id, 'username': user.username, 'balance': user.balance_cents / 100}


def issue_session(db, user, response):
    token = secrets.token_urlsafe(32)
    db.query(AuthSession).filter(AuthSession.expires_at <= utcnow()).delete(synchronize_session=False)
    db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                       expires_at=utcnow() + timedelta(hours=8)))
    response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True, secure=COOKIE_SECURE,
                        samesite='strict', path='/api')


def identity(req, user):
    if req.user_id is not None and req.user_id != user.id:
        raise HTTPException(403, 'לא ניתן לבצע פעולה בשם משתמש אחר')


def fingerprint(action, req):
    body = req.model_dump(mode='json', exclude={'request_id'})
    # Keep existing retry keys valid for requests made before these guards existed.
    for optional_guard in ('tournament_id', 'game_number'):
        if body.get(optional_guard) is None:
            body.pop(optional_guard, None)
    return hashlib.sha256(json.dumps([action, body], sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def replay(db, user, req, action):
    identity(req, user)
    digest = fingerprint(action, req)
    previous = db.query(Mutation).filter_by(user_id=user.id, request_id=str(req.request_id)).first()
    if previous:
        if previous.fingerprint != digest:
            raise HTTPException(409, 'מזהה הבקשה כבר שימש לפעולה אחרת')
        return json.loads(previous.response_json), digest
    return None, digest


def finish(db, user, req, digest, result):
    db.add(Mutation(user_id=user.id, request_id=str(req.request_id), fingerprint=digest,
                    response_json=json.dumps(result, ensure_ascii=False)))
    db.commit()
    return result


def active_tournament(db, user, expected_id=None):
    tournament = db.query(Tournament).filter_by(owner_id=user.id, status='active').first()
    if expected_id is not None and (tournament is None or tournament.id != expected_id):
        raise HTTPException(409, 'העונה השתנתה. רעננו את הנתונים לפני הפעולה')
    if tournament is None:
        tournament = Tournament(owner_id=user.id)
        db.add(tournament)
        db.flush()
    return tournament


def series_games(db, tournament, sid):
    return db.query(GameHistory).filter_by(tournament_id=tournament.id, series_id=sid).order_by(GameHistory.game_number, GameHistory.id).all()


def winner_of(games, t1, t2):
    if not t1 or not t2:
        return None
    counts = Counter(g.winner for g in games)
    return t1 if counts[t1] >= 4 else t2 if counts[t2] >= 4 else None


def bracket_state(db, tournament):
    histories = db.query(GameHistory).filter_by(tournament_id=tournament.id).order_by(GameHistory.game_number, GameHistory.id).all()
    by_series = {}
    for game in histories:
        by_series.setdefault(game.series_id, []).append(game)
    wt, et = engine_nba.west_teams, engine_nba.east_teams
    seeds = [(1, 8), (4, 5), (3, 6), (2, 7)]
    rounds = [[(f'{side} {a} vs {b}', teams[a], teams[b]) for side, teams in [('West', wt), ('East', et)] for a, b in seeds]]
    winners = lambda matches: [winner_of(by_series.get(sid, []), a, b) for sid, a, b in matches]
    r1 = winners(rounds[0])
    rounds.append([(f'{side} Semi {i+1}', r1[offset + i*2], r1[offset + i*2 + 1]) for side, offset in [('West', 0), ('East', 4)] for i in range(2)])
    r2 = winners(rounds[1])
    rounds.append([('West Finals', r2[0], r2[1]), ('East Finals', r2[2], r2[3])])
    r3 = winners(rounds[2])
    rounds.append([('NBA Finals', r3[0], r3[1])])
    champion = winner_of(by_series.get('NBA Finals', []), *r3)
    active = next((i for i, matches in enumerate(rounds, 1) if not all(winners(matches))), 4)
    return active, rounds, by_series, champion


def get_round_matchups(db, tournament):
    active, rounds, _, _ = bracket_state(db, tournament)
    return active, rounds[active - 1]


def require_matchup(db, tournament, req):
    round_number, matches = get_round_matchups(db, tournament)
    match = next((m for m in matches if m[0] == req.matchup), None)
    if not match or not match[1] or not match[2]:
        raise HTTPException(409, 'הסדרה אינה פעילה')
    _, t1, t2 = match
    if ((getattr(req, 'team1', None) is not None and req.team1 != t1)
            or (getattr(req, 'team2', None) is not None and req.team2 != t2)):
        raise HTTPException(422, 'הקבוצות אינן תואמות לסדרה')
    games = series_games(db, tournament, req.matchup)
    if winner_of(games, t1, t2):
        raise HTTPException(409, 'הסדרה כבר הסתיימה')
    if len(games) >= 7 or [g.game_number for g in games] != list(range(1, len(games) + 1)):
        raise HTTPException(409, 'היסטוריית הסדרה אינה תקינה')
    return round_number, t1, t2, games


def futures_quotes(state):
    _, rounds, by_series, champion = state
    if champion:
        return []
    advancing = [{team: 1.0} for _, t1, t2 in rounds[0] for team in (t1, t2)]
    for matches in rounds:
        next_round = []
        for (sid, t1, t2), left, right in zip(matches, advancing[::2], advancing[1::2], strict=True):
            games = by_series.get(sid, [])
            winner = winner_of(games, t1, t2)
            if winner:
                next_round.append({winner: 1.0})
                continue
            distribution = defaultdict(float)
            for team1, left_probability in left.items():
                for team2, right_probability in right.items():
                    matchup_probability = left_probability * right_probability
                    series_probability = engine_nba.series_win_probability(team1, team2, games)
                    distribution[team1] += matchup_probability * series_probability
                    distribution[team2] += matchup_probability * (1 - series_probability)
            next_round.append(distribution)
        advancing = next_round
    return [{'team': team, 'odds': odds_for_probability(probability)}
            for team, probability in sorted(advancing[0].items()) if probability > 0]


def quote_bet(db, tournament, req):
    if req.bet_type == 'futures_champion':
        if req.matchup != 'NBA Finals' or req.game_number != 0:
            raise HTTPException(422, 'הימור אליפות דורש שוק אליפות ומספר משחק 0')
        quote = next((q for q in futures_quotes(bracket_state(db, tournament)) if q['team'] == req.team_bet_on), None)
        if not quote:
            raise HTTPException(409, 'שוק האליפות סגור או שהקבוצה הודחה')
        return quote['odds'], None
    _, t1, t2, games = require_matchup(db, tournament, req)
    if req.game_number != len(games) + 1:
        raise HTTPException(409, 'ניתן להמר רק על המשחק הבא שטרם שוחק')
    odds = engine_nba.calculate_advanced_odds(t1, t2, series_history=games)
    if req.bet_type in ('moneyline', 'series_winner'):
        if req.team_bet_on not in (t1, t2):
            raise HTTPException(422, 'יש לבחור קבוצה שמשתתפת בסדרה')
        return odds[req.bet_type][req.team_bet_on], None
    if req.bet_type == 'spread':
        if req.team_bet_on not in (t1, t2):
            raise HTTPException(422, 'קבוצה לא תקינה')
        key = 'team1_spread' if req.team_bet_on == t1 else 'team2_spread'
        return odds['spread']['odds'], odds['spread'][key]
    if req.team_bet_on not in ('Over', 'Under'):
        raise HTTPException(422, 'יש לבחור מעל או מתחת לקו')
    return odds['over_under_points']['over_odds' if req.team_bet_on == 'Over' else 'under_odds'], odds['over_under_points']['line']


def pay_bet(user, bet, status):
    if bet.status != 'pending':
        return
    bet.status = status
    paid = bet.potential_win_cents if status == 'won' else bet.amount_cents if status in ('push', 'cancelled') else 0
    bet.paid_out_cents = paid
    user.balance_cents += paid


def simulate_one(db, user, tournament, sid, expected_game=None):
    req = SeriesRequest(matchup=sid)
    round_number, t1, t2, games = require_matchup(db, tournament, req)
    number = len(games) + 1
    if expected_game is not None and expected_game != number:
        raise HTTPException(409, 'מספר המשחק השתנה. רעננו את הנתונים')
    stats = engine_nba.generate_game_stats(t1, t2, series_history=games)
    if (stats['winner'] not in (t1, t2) or stats['t1_pts'] == stats['t2_pts']
            or stats['winner'] != (t1 if stats['t1_pts'] > stats['t2_pts'] else t2)):
        raise RuntimeError('Simulation produced an invalid result')
    game = GameHistory(tournament_id=tournament.id, series_id=sid, round_number=round_number,
                       game_number=number, team1=t1, team2=t2, team1_pts=stats['t1_pts'],
                       team2_pts=stats['t2_pts'], winner=stats['winner'],
                       team1_rebounds=stats['t1_rebounds'], team2_rebounds=stats['t2_rebounds'])
    db.add(game)
    db.flush()  # bounded loops see the new game before the next iteration
    series_champion = winner_of([*games, game], t1, t2)
    pending = db.query(Bet).filter_by(tournament_id=tournament.id, user_id=user.id, status='pending').all()
    for bet in pending:
        if bet.bet_type == 'futures_champion':
            if sid == 'NBA Finals' and series_champion:
                pay_bet(user, bet, 'won' if bet.team_bet_on == series_champion else 'lost')
            elif series_champion and bet.team_bet_on == (t2 if series_champion == t1 else t1):
                pay_bet(user, bet, 'lost')
        elif bet.matchup == sid and bet.bet_type == 'series_winner':
            if series_champion:
                pay_bet(user, bet, 'won' if bet.team_bet_on == series_champion else 'lost')
        elif bet.matchup == sid and bet.game_number == number:
            if bet.bet_type == 'moneyline':
                status = 'won' if bet.team_bet_on == stats['winner'] else 'lost'
            elif bet.bet_type == 'spread':
                margin = stats['t1_pts'] - stats['t2_pts']
                adjusted = (margin if bet.team_bet_on == t1 else -margin) + bet.target_value
                status = 'push' if adjusted == 0 else 'won' if adjusted > 0 else 'lost'
            else:
                difference = stats['total_points'] - bet.target_value
                status = 'push' if difference == 0 else 'won' if ((difference > 0) == (bet.team_bet_on == 'Over')) else 'lost'
            pay_bet(user, bet, status)
    db.flush()
    return {**stats, 'series_id': sid, 'game_number': number}

@app.get('/api/health')
def health():
    return {'status': 'ok', 'data_source': getattr(engine_nba, 'data_source', 'season snapshot')}

def mail_quota(db, request, email):
    now = utcnow()
    source = request.client.host if request.client else 'local'
    for scope, value, limit in (('source', source, 8), ('email', email, 3)):
        key = hashlib.sha256(f'email-mail:{scope}:{value}'.encode()).hexdigest()
        if db.get_bind().dialect.name == 'postgresql':
            db.execute(postgres_insert(LoginAttempt).values(key=key, failures=0, window_start=now)
                       .on_conflict_do_nothing(index_elements=[LoginAttempt.key]))
        attempt = db.query(LoginAttempt).filter_by(key=key).with_for_update().first()
        if attempt is None:
            attempt = LoginAttempt(key=key, failures=0, window_start=now)
            db.add(attempt)
        if now - attempt.window_start >= timedelta(minutes=15):
            attempt.failures, attempt.window_start = 0, now
        if attempt.failures >= limit:
            raise HTTPException(429, 'יותר מדי בקשות למייל. נסו שוב בעוד 15 דקות', headers={'Retry-After': '900'})
        attempt.failures += 1


def prepare_email_verification(db, user, email):
    if db.query(AccountEmail).filter(AccountEmail.email == email, AccountEmail.verified_at.is_not(None),
                                    AccountEmail.user_id != user.id).first():
        raise HTTPException(409, 'לא ניתן לשייך את כתובת המייל הזו לחשבון')
    entry = db.get(AccountEmail, user.id)
    if entry is None:
        entry = AccountEmail(user_id=user.id)
        db.add(entry)
    code = secrets.token_urlsafe(32)
    entry.email, entry.verified_at = email, None
    entry.verification_hash = hashlib.sha256(code.encode('ascii')).hexdigest()
    entry.verification_expires_at = utcnow() + timedelta(minutes=30)
    # Links sent to a previous address must not survive an address change.
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.token_hash.startswith('reset:')).delete(synchronize_session=False)
    email_delivery.send_link(email, code, 'verify-email')


@app.post('/api/register', status_code=201)
def register(req: RegisterRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter_by(username=req.username).first():
        raise HTTPException(409, 'שם המשתמש כבר קיים')
    if req.email:
        email_delivery.settings()
        mail_quota(db, request, req.email)
    user = User(username=req.username, hashed_password=get_password_hash(req.password), balance_cents=100000)
    db.add(user)
    db.flush()
    db.add(Tournament(owner_id=user.id))
    if req.email:
        prepare_email_verification(db, user, req.email)
    issue_session(db, user, response)
    db.commit()
    return wallet(user)


@app.get('/api/me/email')
def account_email(user: User = Depends(current_user), db: Session = Depends(get_db)):
    entry = db.get(AccountEmail, user.id)
    return {'email': entry.email if entry else None, 'verified': bool(entry and entry.verified_at),
            'delivery_configured': email_delivery.is_configured()}


@app.post('/api/me/email')
def bind_email(req: BindEmailRequest, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(403, 'הסיסמה הנוכחית שגויה')
    email_delivery.settings()
    mail_quota(db, request, req.email)
    prepare_email_verification(db, user, req.email)
    db.commit()
    return {'status': 'sent'}


@app.post('/api/verify-email')
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    digest = hashlib.sha256(req.code.encode('ascii')).hexdigest()
    entry = db.query(AccountEmail).filter_by(verification_hash=digest).first()
    invalid = HTTPException(400, 'קישור האימות אינו תקף או שפג תוקפו')
    if entry is None:
        raise invalid
    db.query(User).filter_by(id=entry.user_id).with_for_update().one()
    db.refresh(entry)
    if entry.verification_hash != digest or entry.verification_expires_at is None or entry.verification_expires_at <= utcnow():
        raise invalid
    entry.verified_at = utcnow()
    entry.verification_hash = entry.verification_expires_at = None
    db.commit()
    return {'status': 'verified'}


@app.post('/api/forgot-password')
def forgot_password(req: EmailRequest, request: Request, db: Session = Depends(get_db)):
    email_delivery.settings()
    user = db.query(User).join(AccountEmail, AccountEmail.user_id == User.id).filter(
        AccountEmail.email == req.email, AccountEmail.verified_at.is_not(None)).with_for_update().first()
    mail_quota(db, request, req.email)
    if user:
        code = issue_recovery_code(db, user.username)
        email_delivery.send_link(req.email, code, 'reset-password')
    db.commit()
    # Never disclose whether the address has a registered/verified account.
    return {'status': 'accepted'}

@app.post('/api/login')
def login(req: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username).with_for_update().first()
    # Verified password recovery starts a fresh window for the new credentials.
    key_parts = [request.client.host if request.client else 'local', req.username,
                 user.hashed_password if user else None]
    key = hashlib.sha256(json.dumps(key_parts).encode()).hexdigest()
    now = utcnow()
    if db.get_bind().dialect.name == 'postgresql':
        # SELECT FOR UPDATE cannot lock a counter that does not exist yet.
        db.execute(postgres_insert(LoginAttempt).values(key=key, failures=0, window_start=now)
                   .on_conflict_do_nothing(index_elements=[LoginAttempt.key]))
    attempt = db.query(LoginAttempt).filter_by(key=key).with_for_update().first()
    if attempt and (now - attempt.window_start).total_seconds() >= 900:
        attempt.failures, attempt.window_start = 0, now
    if attempt and attempt.failures >= 10:
        raise HTTPException(429, 'יותר מדי ניסיונות. נסו שוב בעוד 15 דקות', headers={'Retry-After': '900'})
    if not verify_password(req.password, user.hashed_password if user else None):
        if attempt is None:
            attempt = LoginAttempt(key=key, failures=0, window_start=now)
            db.add(attempt)
        attempt.failures += 1
        db.commit()
        raise HTTPException(401, 'שם המשתמש או הסיסמה שגויים')
    if attempt:
        attempt.failures = 0
    issue_session(db, user, response)
    db.commit()
    return wallet(user)

@app.post('/api/reset-password')
def reset_password(req: PasswordResetRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    key = recovery_key(req.code)
    recovery = db.get(AuthSession, key)
    invalid = HTTPException(400, 'קוד האיפוס אינו תקף או שפג תוקפו')
    if recovery is None or recovery.expires_at <= utcnow():
        raise invalid
    user = db.query(User).filter_by(id=recovery.user_id).with_for_update().first()
    recovery = db.get(AuthSession, key, populate_existing=True)
    if user is None or recovery is None or recovery.expires_at <= utcnow():
        raise invalid
    token = request.cookies.get(COOKIE)
    browser_session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
    clear_cookie = browser_session is not None and browser_session.user_id == user.id
    user.hashed_password = get_password_hash(req.password)
    db.query(AuthSession).filter_by(user_id=user.id).delete(synchronize_session=False)
    db.commit()
    if clear_cookie:
        response.delete_cookie(COOKIE, path='/api', secure=COOKIE_SECURE, httponly=True, samesite='strict')
    return {'status': 'ok'}

@app.post('/api/logout')
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE, '')
    db.query(AuthSession).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id).delete()
    db.commit()
    response.delete_cookie(COOKIE, path='/api', secure=COOKIE_SECURE, httponly=True, samesite='strict')
    return {'message': 'התנתקת בהצלחה'}

@app.get('/api/me')
def me(user: User = Depends(current_user)):
    return wallet(user)

@app.get('/api/user/{user_id}')
def legacy_user(user_id: int, user: User = Depends(current_user)):
    if user_id != user.id:
        raise HTTPException(403, 'אין הרשאה למשתמש זה')
    return wallet(user)

def market_lines(tournament, state):
    active, rounds, by_series, champion = state
    lines = []
    for sid, t1, t2 in rounds[active - 1]:
        games = by_series.get(sid, [])
        if not t1 or not t2 or winner_of(games, t1, t2):
            continue
        counts = Counter(g.winner for g in games)
        lines.append({'series_id': sid, 'current_round': active, 'team1': t1, 'team2': t2,
                      'home_team': engine_nba.home_team(t1, t2, len(games) + 1),
                      'series_score': f'{counts[t1]} - {counts[t2]}', 'next_game_number': len(games) + 1,
                      'is_unlocked': True, 'conference': 'west' if sid.startswith('West ') else 'east' if sid.startswith('East ') else 'finals',
                      'odds': engine_nba.calculate_advanced_odds(t1, t2, series_history=games)})
    return {'active_round': active, 'betting_lines': lines, 'tournament_id': tournament.id, 'champion': champion,
            'data_source': getattr(engine_nba, 'data_source', 'season snapshot')}

@app.get('/api/dashboard')
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tournament = active_tournament(db, user)
    state = bracket_state(db, tournament)
    result = {'user': wallet(user), 'lines': market_lines(tournament, state), 'futures_lines': futures_quotes(state)}
    db.commit()
    return result

@app.get('/api/betting-lines')
def betting_lines(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tournament = active_tournament(db, user)
    result = market_lines(tournament, bracket_state(db, tournament))
    db.commit()
    return result

@app.get('/api/futures-lines')
def futures_lines(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tournament = active_tournament(db, user)
    lines = futures_quotes(bracket_state(db, tournament))
    db.commit()
    return {'futures_lines': lines}

@app.post('/api/place-bet')
def place_bet(req: PlaceBetRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    previous, digest = replay(db, user, req, 'bet')
    if previous is not None:
        return previous
    tournament = active_tournament(db, user, req.tournament_id)
    odds, target = quote_bet(db, tournament, req)
    if (req.odds is not None and not math.isclose(req.odds, odds, abs_tol=.004, rel_tol=0)) or (
            req.target_value is not None and (target is None or not math.isclose(req.target_value, target, abs_tol=.0001, rel_tol=0))):
        raise HTTPException(409, 'יחס ההימור או הקו השתנו. בחרו הצעה מעודכנת')
    cents = int(req.amount * 100)
    if user.balance_cents < cents:
        raise HTTPException(400, 'אין מספיק יתרה מדומה')
    payout = int((Decimal(cents) * Decimal(str(odds))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    user.balance_cents -= cents
    bet = Bet(user_id=user.id, tournament_id=tournament.id, request_id=str(req.request_id), request_fingerprint=digest,
              matchup=req.matchup, game_number=req.game_number, bet_type=req.bet_type, team_bet_on=req.team_bet_on,
              target_value=target, amount_cents=cents, odds=odds, potential_win_cents=payout)
    db.add(bet)
    db.flush()
    return finish(db, user, req, digest, {'message': 'ההימור נקלט', 'bet_id': bet.id,
                                        'new_balance': user.balance_cents / 100, 'potential_win': payout / 100})

@app.post('/api/simulate-game')
def simulate_single_game(req: GameRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    previous, digest = replay(db, user, req, 'game')
    if previous is not None:
        return previous
    tournament = active_tournament(db, user, req.tournament_id)
    require_matchup(db, tournament, req)
    result = simulate_one(db, user, tournament, req.matchup, req.game_number)
    return finish(db, user, req, digest, {'game_result': result, 'message': 'המשחק הסתיים', 'new_balance': user.balance_cents / 100})

@app.post('/api/simulate-series-auto')
def simulate_series_auto(req: SeriesRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    previous, digest = replay(db, user, req, 'series')
    if previous is not None:
        return previous
    tournament = active_tournament(db, user, req.tournament_id)
    _, t1, t2, games = require_matchup(db, tournament, req)
    if req.game_number is not None and req.game_number != len(games) + 1:
        raise HTTPException(409, 'מספר המשחק השתנה. רעננו את הנתונים')
    results = []
    for _ in range(7):
        if winner_of(series_games(db, tournament, req.matchup), t1, t2):
            break
        results.append(simulate_one(db, user, tournament, req.matchup))
    champion = winner_of(series_games(db, tournament, req.matchup), t1, t2)
    if not champion:
        raise HTTPException(409, 'הסדרה לא הגיעה להכרעה תקינה')
    return finish(db, user, req, digest, {'completed': True, 'winner': champion, 'results': results,
                                        'message': 'הסדרה הסתיימה', 'new_balance': user.balance_cents / 100})

@app.post('/api/simulate-tournament-auto')
def simulate_tournament_auto(req: ActionRequest | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    req = req or ActionRequest()
    previous, digest = replay(db, user, req, 'tournament')
    if previous is not None:
        return previous
    tournament = active_tournament(db, user, req.tournament_id)
    results = []
    for _ in range(105):
        active, rounds, by_series, champion = bracket_state(db, tournament)
        if champion:
            break
        matches = rounds[active - 1]
        match = next((m for m in matches if m[1] and m[2] and not winner_of(by_series.get(m[0], []), m[1], m[2])), None)
        if not match:
            raise HTTPException(409, 'הטורניר אינו יכול להתקדם')
        results.append(simulate_one(db, user, tournament, match[0]))
    _, _, _, champion = bracket_state(db, tournament)
    if not champion:
        raise HTTPException(409, 'הטורניר לא הושלם')
    return finish(db, user, req, digest, {'completed': True, 'champion': champion, 'games_played': len(results),
                                        'message': 'הטורניר הסתיים', 'new_balance': user.balance_cents / 100})

@app.post('/api/reset-tournament')
def reset_tournament(req: ActionRequest | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    req = req or ActionRequest()
    previous, digest = replay(db, user, req, 'reset')
    if previous is not None:
        return previous
    tournament = active_tournament(db, user, req.tournament_id)
    pending = db.query(Bet).filter_by(tournament_id=tournament.id, user_id=user.id, status='pending').all()
    _, rounds, by_series, _ = bracket_state(db, tournament)
    eliminated = {
        t2 if winner == t1 else t1
        for matches in rounds
        for sid, t1, t2 in matches
        if (winner := winner_of(by_series.get(sid, []), t1, t2))
    }
    refund = 0
    for bet in pending:
        if bet.bet_type == 'futures_champion' and bet.team_bet_on in eliminated:
            pay_bet(user, bet, 'lost')
        else:
            refund += bet.amount_cents
            pay_bet(user, bet, 'cancelled')
    tournament.status = 'archived'
    db.flush()
    new_tournament = Tournament(owner_id=user.id)
    db.add(new_tournament)
    db.flush()
    return finish(db, user, req, digest, {'message': 'נפתח טורניר חדש. ההיסטוריה נשמרה', 'tournament_id': new_tournament.id,
                                        'refund': refund / 100, 'new_balance': user.balance_cents / 100})

@app.post('/api/deposit')
@app.post('/api/reload-bank')
def reload_bank(req: ActionRequest | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    req = req or ActionRequest()
    previous, digest = replay(db, user, req, 'reload')
    if previous is not None:
        return previous
    if req.tournament_id is not None:
        active_tournament(db, user, req.tournament_id)
    if user.balance_cents > 100:
        raise HTTPException(400, 'מילוי יתרה זמין ביתרה של דולר מדומה אחד או פחות')
    if user.last_reload and (utcnow() - user.last_reload).total_seconds() < 10:
        raise HTTPException(429, 'יש להמתין 10 שניות בין מילויים', headers={'Retry-After': '10'})
    user.balance_cents += 100000
    user.last_reload = utcnow()
    return finish(db, user, req, digest, {'message': 'היתרה המדומה מולאה', 'new_balance': user.balance_cents / 100})

@app.get('/api/tournament-status')
def tournament_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tournament = active_tournament(db, user)
    active, rounds, by_series, champion = bracket_state(db, tournament)
    def card(match):
        sid, t1, t2 = match
        counts = Counter(g.winner for g in by_series.get(sid, []))
        return {'series_id': sid, 't1': {'name': t1 or 'TBD', 'wins': counts[t1]}, 't2': {'name': t2 or 'TBD', 'wins': counts[t2]}}
    bracket = {side: {f'r{r}': [card(m) for m in rounds[r-1] if m[0].startswith(prefix)] for r in (1, 2, 3)} for side, prefix in [('west', 'West '), ('east', 'East ')]}
    bracket.update({'finals': card(rounds[3][0]), 'champion': champion, 'active_round': active, 'tournament_id': tournament.id})
    db.commit()
    return bracket

@app.get('/api/me/history')
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    bets = db.query(Bet).filter_by(user_id=user.id).order_by(Bet.id.desc()).all()
    return {'history': [{'id': b.id, 'tournament_id': b.tournament_id, 'matchup': b.matchup,
                         'game_number': b.game_number, 'bet_type': b.bet_type, 'team_bet_on': b.team_bet_on,
                         'target_value': b.target_value, 'amount': b.amount_cents / 100, 'odds': b.odds,
                         'potential_win': b.potential_win_cents / 100, 'paid_out': b.paid_out_cents / 100,
                         'status': b.status, 'created_at': b.created_at.isoformat() + 'Z'} for b in bets]}

@app.get('/api/user/{user_id}/history')
def legacy_history(user_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user_id != user.id:
        raise HTTPException(403, 'אין הרשאה למשתמש זה')
    return history(user, db)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
