"""Non-destructive legacy SQLite export into a NEW version-2 database.

Original shared games are copied into each owner's archived tournament.
Pending bets are cancelled/refunded once. The source is never modified.
Invalid legacy rows abort the export rather than silently losing records.
"""
import argparse
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.db.database import Base
from backend.db.models import Bet, GameHistory, Tournament, User

def cents(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError('Invalid legacy monetary value; source was preserved')
    return int((number * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def migrate(source: Path, destination: Path):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == destination:
        raise ValueError('Destination must differ from source')
    # Reserve exclusively: never overwrite, even if a second migration races.
    with destination.open('xb'):
        pass
    target_engine = create_engine(f'sqlite:///{destination.as_posix()}')
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as old:
            old.row_factory = sqlite3.Row
            old.execute('BEGIN')  # consistent read-only snapshot, including WAL
            users = [dict(r) for r in old.execute('SELECT * FROM users ORDER BY id')]
            bets = [dict(r) for r in old.execute('SELECT * FROM bets ORDER BY id')]
            games = [dict(r) for r in old.execute('SELECT * FROM game_history ORDER BY id')]
        known_ids = {u['id'] for u in users}
        if any(b['user_id'] not in known_ids for b in bets):
            raise ValueError('Legacy bets have orphan owners; resolve them before export')
        Base.metadata.create_all(target_engine)
        with Session(target_engine) as db, db.begin():
            for old_user in users:
                own_bets = [b for b in bets if b['user_id'] == old_user['id']]
                refund = sum(cents(b['amount']) for b in own_bets if b['status'] == 'pending')
                user = User(id=old_user['id'], username=old_user['username'],
                            hashed_password=old_user['hashed_password'],
                            balance_cents=cents(old_user['balance']) + refund)
                if old_user.get('last_reload'):
                    last = datetime.fromisoformat(str(old_user['last_reload']))
                    user.last_reload = (last.astimezone(timezone.utc).replace(tzinfo=None)
                                        if last.tzinfo else last)
                db.add(user)
                db.flush()
                archived = Tournament(owner_id=user.id, status='archived')
                active = Tournament(owner_id=user.id, status='active')
                db.add_all([archived, active])
                db.flush()
                for b in own_bets:
                    amount, payout = cents(b['amount']), cents(b['potential_win'])
                    status = 'cancelled' if b['status'] == 'pending' else b['status']
                    paid = payout if status == 'won' else amount if status in ('push', 'cancelled') else 0
                    db.add(Bet(id=b['id'], user_id=user.id, tournament_id=archived.id,
                               request_id=str(uuid4()), request_fingerprint='legacy-import',
                               matchup=b['matchup'], game_number=b['game_number'], bet_type=b['bet_type'],
                               team_bet_on=b['team_bet_on'], target_value=b['target_value'],
                               amount_cents=amount, odds=b['odds'], potential_win_cents=payout,
                               paid_out_cents=paid, status=status))
                for g in games:
                    columns = {k: g[k] for k in ('series_id', 'round_number', 'game_number', 'team1', 'team2',
                                                  'team1_pts', 'team2_pts', 'team1_rebounds', 'team2_rebounds', 'winner')}
                    db.add(GameHistory(tournament_id=archived.id, **columns))
        return {'users': len(users), 'bets': len(bets), 'source_games': len(games), 'destination': str(destination)}
    except Exception:
        # Keep a failed export for diagnosis. The source remains untouched;
        # choose a fresh destination after fixing invalid legacy records.
        raise
    finally:
        target_engine.dispose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(migrate(args.source, args.destination))
