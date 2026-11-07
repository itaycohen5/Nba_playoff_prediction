from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index, text
from backend.db.database import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(40), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    balance_cents = Column(BigInteger, nullable=False, default=100000)
    last_reload = Column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint('balance_cents >= 0'),)

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

class AccountEmail(Base):
    __tablename__ = 'account_emails'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    email = Column(String(254), nullable=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    verification_hash = Column(String(64), nullable=True, unique=True)
    verification_expires_at = Column(DateTime, nullable=True)
    __table_args__ = (
        Index('one_verified_account_per_email', 'email', unique=True,
              sqlite_where=text('verified_at IS NOT NULL'), postgresql_where=text('verified_at IS NOT NULL')),
    )

class LoginAttempt(Base):
    __tablename__ = 'login_attempts'
    key = Column(String(64), primary_key=True)
    failures = Column(Integer, nullable=False, default=0)
    window_start = Column(DateTime, nullable=False, default=utcnow)

class Tournament(Base):
    __tablename__ = 'tournaments'
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    status = Column(String(16), nullable=False, default='active')
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')"),
        Index('one_active_tournament_per_owner', 'owner_id', unique=True,
              sqlite_where=text("status = 'active'"), postgresql_where=text("status = 'active'")),
    )

class Mutation(Base):
    __tablename__ = 'mutations'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    request_id = Column(String(36), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    response_json = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'request_id'),)

class Bet(Base):
    __tablename__ = 'bets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id'), nullable=False, index=True)
    request_id = Column(String(36), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    matchup = Column(String(80), nullable=False)
    game_number = Column(Integer, nullable=False)
    bet_type = Column(String(32), nullable=False)
    team_bet_on = Column(String(80), nullable=False)
    target_value = Column(Float, nullable=True)
    amount_cents = Column(BigInteger, nullable=False)
    odds = Column(Float, nullable=False)
    potential_win_cents = Column(BigInteger, nullable=False)
    paid_out_cents = Column(BigInteger, nullable=False, default=0)
    status = Column(String(16), nullable=False, default='pending')
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint('user_id', 'request_id'),
        CheckConstraint('game_number BETWEEN 0 AND 7'),
        CheckConstraint('amount_cents > 0 AND potential_win_cents >= 0 AND paid_out_cents >= 0'),
        CheckConstraint('odds >= 1'),
        CheckConstraint("status IN ('pending','won','lost','push','cancelled')"),
        CheckConstraint("bet_type IN ('moneyline','spread','over_under_points','series_winner','futures_champion')"),
    )

class GameHistory(Base):
    __tablename__ = 'game_history'
    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id'), nullable=False, index=True)
    series_id = Column(String(80), nullable=False)
    round_number = Column(Integer, nullable=False)
    game_number = Column(Integer, nullable=False)
    team1 = Column(String(80), nullable=False)
    team2 = Column(String(80), nullable=False)
    team1_pts = Column(Integer, nullable=False)
    team2_pts = Column(Integer, nullable=False)
    team1_rebounds = Column(Integer, nullable=True)
    team2_rebounds = Column(Integer, nullable=True)
    winner = Column(String(80), nullable=False)
    __table_args__ = (
        UniqueConstraint('tournament_id', 'series_id', 'game_number'),
        CheckConstraint('game_number BETWEEN 1 AND 7'),
        CheckConstraint('round_number BETWEEN 1 AND 4'),
        CheckConstraint('team1_pts >= 0 AND team2_pts >= 0'),
        CheckConstraint('team1 <> team2'),
        CheckConstraint('winner = team1 OR winner = team2'),
    )
