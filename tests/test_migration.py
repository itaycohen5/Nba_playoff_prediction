"""Tests for the explicit, non-destructive SQLite legacy migration."""
import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

# Importing this module alone must never point an application import at .env.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="nba-migration-")
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "legacy.db"
        self.destination = Path(self.directory.name) / "migrated.db"
        with closing(sqlite3.connect(self.source)) as db:
            db.executescript("""
                CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE,
                    hashed_password TEXT, balance FLOAT, last_reload DATETIME);
                CREATE TABLE bets (id INTEGER PRIMARY KEY, user_id INTEGER, matchup TEXT,
                    game_number INTEGER, bet_type TEXT, team_bet_on TEXT, target_value FLOAT,
                    amount FLOAT, odds FLOAT, potential_win FLOAT, status TEXT);
                CREATE TABLE game_history (id INTEGER PRIMARY KEY, series_id TEXT,
                    round_number INTEGER, game_number INTEGER, team1 TEXT, team2 TEXT,
                    team1_pts INTEGER, team2_pts INTEGER, team1_rebounds INTEGER,
                    team2_rebounds INTEGER, winner TEXT);
            """)
            db.execute("INSERT INTO users VALUES(7,'legacy_user','opaque-test-hash',123.45,NULL)")
            db.execute("INSERT INTO users VALUES(8,'second_user','second-test-hash',900.0,NULL)")
            db.execute("INSERT INTO bets VALUES(11,7,'West 1 vs 8',2,'moneyline','Thunder',NULL,12.34,2.0,24.68,'pending')")
            db.execute("INSERT INTO bets VALUES(12,7,'West 1 vs 8',1,'moneyline','Thunder',NULL,10.0,2.0,20.0,'won')")
            db.execute("INSERT INTO bets VALUES(13,8,'West 1 vs 8',2,'moneyline','Suns',NULL,20.0,2.0,40.0,'pending')")
            db.execute("INSERT INTO game_history VALUES(21,'West 1 vs 8',1,1,'Thunder','Suns',110,100,44,40,'Thunder')")
            db.commit()
        self.source_digest = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def migrate(self):
        from scripts.migrate_legacy import migrate
        return migrate(self.source, self.destination)

    def test_preserves_source_and_users_cancels_and_refunds_pending(self):
        self.migrate()
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_digest)
        self.assertTrue(self.destination.is_file())
        with closing(sqlite3.connect(self.destination)) as db:
            db.row_factory = sqlite3.Row
            users = {row["id"]: row for row in db.execute("SELECT * FROM users")}
            self.assertEqual(users[7]["username"], "legacy_user")
            self.assertEqual(users[7]["hashed_password"], "opaque-test-hash")
            self.assertEqual(users[7]["balance_cents"], 13579)
            self.assertEqual(users[8]["balance_cents"], 92000)
            bets = list(db.execute("SELECT * FROM bets WHERE user_id=7 ORDER BY id"))
            self.assertEqual(len(bets), 2)
            self.assertEqual({row["status"] for row in bets}, {"cancelled", "won"})
            cancelled = next(row for row in bets if row["status"] == "cancelled")
            self.assertEqual(cancelled["amount_cents"], 1234)
            self.assertEqual(cancelled["potential_win_cents"], 2468)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_game_history_is_archived_per_user_and_new_tournament_is_clean(self):
        self.migrate()
        with closing(sqlite3.connect(self.destination)) as db:
            db.row_factory = sqlite3.Row
            for user_id in (7, 8):
                tournaments = list(db.execute("SELECT * FROM tournaments WHERE owner_id=?", (user_id,)))
                self.assertEqual(len(tournaments), 2)
                active = next(row for row in tournaments if row["status"] == "active")
                archived = next(row for row in tournaments if row["status"] != "active")
                self.assertEqual(db.execute("SELECT count(*) FROM game_history WHERE tournament_id=?", (active["id"],)).fetchone()[0], 0)
                games = list(db.execute("SELECT * FROM game_history WHERE tournament_id=?", (archived["id"],)))
                self.assertEqual(len(games), 1)
                self.assertEqual(games[0]["winner"], "Thunder")
                self.assertEqual(games[0]["team1_rebounds"], 44)
                wrong_tournament_bets = db.execute("SELECT count(*) FROM bets WHERE user_id=? AND tournament_id != ?", (user_id, archived["id"])).fetchone()[0]
                self.assertEqual(wrong_tournament_bets, 0)

    def test_rerun_cannot_overwrite_or_refund_twice(self):
        self.migrate()
        digest = hashlib.sha256(self.destination.read_bytes()).hexdigest()
        with self.assertRaises(FileExistsError):
            self.migrate()
        self.assertEqual(hashlib.sha256(self.destination.read_bytes()).hexdigest(), digest)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_digest)

    def test_missing_source_and_same_path_are_rejected_safely(self):
        from scripts.migrate_legacy import migrate
        with self.assertRaises((FileNotFoundError, ValueError)):
            migrate(self.source.with_name("missing.db"), self.destination)
        self.assertFalse(self.destination.exists())
        with self.assertRaises((FileExistsError, ValueError)):
            migrate(self.source, self.source)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_digest)


if __name__ == "__main__":
    unittest.main()
