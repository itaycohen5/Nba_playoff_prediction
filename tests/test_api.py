"""Isolated API regression suite. Never connects to the project's .env database.

Run from the project root: python -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="nba-regression-")
TEST_DATABASE = Path(TEST_DIRECTORY.name) / "regression.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["COOKIE_SECURE"] = "false"

from fastapi.testclient import TestClient
from backend import api
from backend.db.database import Base, SessionLocal, engine
from backend.db.models import AuthSession, Bet, GameHistory, Tournament, User, utcnow
from backend.db.recovery import issue_recovery_code, recovery_key

if Path(engine.url.database).resolve() != TEST_DATABASE.resolve():
    raise RuntimeError("Refusing to run against a non-test database")


def tearDownModule():
    engine.dispose()
    TEST_DIRECTORY.cleanup()


class APIRegressionTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        self.context = TestClient(api.app, raise_server_exceptions=False)
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def register(self, name="qa_user", client=None):
        client = client or self.client
        result = client.post("/api/register", json={"username": name, "password": "QaPassw0rd!"})
        self.assertIn(result.status_code, (200, 201), result.text)
        # Login explicitly: registration need not create a session.
        result = client.post("/api/login", json={"username": name, "password": "QaPassw0rd!"})
        self.assertEqual(result.status_code, 200, result.text)
        return result

    def me(self, client=None):
        response = (client or self.client).get("/api/me")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def lines(self, client=None):
        response = (client or self.client).get("/api/betting-lines")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["betting_lines"]

    def history(self, client=None):
        response = (client or self.client).get("/api/me/history")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["history"]

    def bet(self, line=None, kind="moneyline", amount=10, **overrides):
        line = line or self.lines()[0]
        body = {
            "request_id": str(uuid4()), "matchup": line["series_id"],
            "game_number": line["next_game_number"], "bet_type": kind,
            "team_bet_on": line["team1"], "amount": amount,
        }
        if kind == "spread":
            body["target_value"] = line["odds"]["spread"]["team1_spread"]
        elif kind == "over_under_points":
            body["team_bet_on"] = "Over"
            body["target_value"] = line["odds"]["over_under_points"]["line"]
        body.update(overrides)
        return body

    @staticmethod
    def game_result(team1, team2, series_history=None):
        return {"winner": team1, "t1_pts": 115, "t2_pts": 100,
                "t1_rebounds": 45, "t2_rebounds": 40, "total_points": 215}

    def play(self, line, client=None):
        return (client or self.client).post("/api/simulate-game", json={
            "matchup": line["series_id"], "game_number": line["next_game_number"],
        })

    def test_dashboard_combines_authenticated_market_state(self):
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)
        self.register()
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json(), {
            "user": self.me(),
            "lines": self.client.get("/api/betting-lines").json(),
            "futures_lines": self.client.get("/api/futures-lines").json()["futures_lines"],
        })

    def test_password_recovery_rotates_credentials_and_revokes_sessions(self):
        user = self.register().json()
        with SessionLocal.begin() as db:
            expired = issue_recovery_code(db, "qa_user")
            db.flush()
            db.get(AuthSession, recovery_key(expired)).expires_at = utcnow() - timedelta(seconds=1)
        new_password = "NewQaPassw0rd!"
        self.assertEqual(self.client.post("/api/reset-password", json={
            "code": expired, "password": new_password,
        }).status_code, 400)
        self.assertEqual(self.me()["id"], user["id"])
        with SessionLocal.begin() as db:
            code = issue_recovery_code(db, "qa_user")
        with TestClient(api.app) as other:
            other.cookies.set("nba_session", code)
            self.assertEqual(other.get("/api/me").status_code, 401)
            self.assertEqual(other.post("/api/reset-password", json={
                "code": code, "password": "NoNumber!",
            }).status_code, 422)
            request = {"code": code, "password": new_password}
            self.assertEqual(other.post("/api/reset-password", json=request).status_code, 200)
            self.assertEqual(other.post("/api/reset-password", json=request).status_code, 400)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(self.client.post("/api/login", json={
            "username": "qa_user", "password": "QaPassw0rd!",
        }).status_code, 401)
        login = self.client.post("/api/login", json={"username": "qa_user", "password": new_password})
        self.assertEqual(login.json(), user)

    def test_session_login_logout_and_wrong_password(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        login = self.register()
        self.assertIn("httponly", login.headers.get("set-cookie", "").lower())
        self.assertEqual(self.me()["balance"], 1000)
        cookies = dict(self.client.cookies)
        self.assertEqual(self.client.post("/api/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        with TestClient(api.app) as other:
            other.cookies.update(cookies)
            self.assertEqual(other.get("/api/me").status_code, 401)
        bad = self.client.post("/api/login", json={"username": "qa_user", "password": "wrongpassword"})
        self.assertEqual(bad.status_code, 401)

    def test_registration_validation_duplicate_and_missing_user(self):
        for body in ({"username": "", "password": ""},
                     {"username": "valid_name", "password": "א" * 80}):
            self.assertEqual(self.client.post("/api/register", json=body).status_code, 422)
        self.register()
        duplicate = self.client.post("/api/register", json={"username": "qa_user", "password": "QaPassw0rd!"})
        self.assertIn(duplicate.status_code, (400, 409))
        response = self.client.get("/api/user/999999")
        self.assertIn(response.status_code, (403, 404))

    def test_validation_never_echoes_credentials_or_serializes_nan(self):
        response = self.client.post('/api/register', json={'username': 'qa_user', 'password': 'short'})
        self.assertEqual(response.status_code, 422, response.text)
        details = response.json()['detail']
        self.assertTrue(any(issue['loc'] == ['body', 'password'] for issue in details))
        self.assertTrue(all(set(issue) == {'loc', 'msg', 'type'} for issue in details))
        self.assertNotIn('"short"', response.text)
        password_message = next(issue['msg'] for issue in details if issue['loc'] == ['body', 'password'])
        for missing in ('לפחות 8 תווים', 'לפחות ספרה אחת', 'לפחות תו מיוחד אחד'):
            self.assertIn(missing, password_message)
        self.assertNotIn('לפחות אות אחת באנגלית', password_message)

        self.register()
        body = self.bet(amount=0)
        content = json.dumps(body).replace('"amount": 0', '"amount": NaN')
        response = self.client.post('/api/place-bet', content=content, headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.me()['balance'], 1000)
        self.assertEqual(self.history(), [])

    def test_expired_session_requires_new_login(self):
        self.register()
        with SessionLocal() as db:
            for session in db.query(AuthSession).all():
                session.expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(self.client.post("/api/reset-tournament").status_code, 401)
        response = self.client.post("/api/login", json={"username": "qa_user", "password": "QaPassw0rd!"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.me()["balance"], 1000)

    def test_login_attempts_are_rate_limited(self):
        # A missing username exercises the same throttle without expensive hashes.
        statuses = []
        for _ in range(12):
            response = self.client.post("/api/login", json={"username": "missing_user", "password": "invalidpassword"})
            statuses.append(response.status_code)
            if response.status_code == 429:
                self.assertGreater(int(response.headers["retry-after"]), 0)
                break
        self.assertIn(429, statuses)
        self.assertTrue(all(status in (401, 429) for status in statuses), statuses)

    def test_all_mutations_and_history_require_authentication(self):
        for path, body in (
            ("/api/place-bet", {"request_id": str(uuid4()), "matchup": "West 1 vs 8", "game_number": 1,
                                "bet_type": "moneyline", "team_bet_on": "fake", "amount": 10}),
            ("/api/simulate-game", {"matchup": "West 1 vs 8", "game_number": 1}),
            ("/api/simulate-series-auto", {"matchup": "West 1 vs 8"}),
            ("/api/simulate-tournament-auto", {}), ("/api/reset-tournament", {}),
            ("/api/reload-bank", {}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json=body).status_code, 401)
        self.assertEqual(self.client.get("/api/me/history").status_code, 401)

    def test_invalid_market_input_never_changes_balance_or_history(self):
        self.register()
        line = self.lines()[0]
        variants = [
            {"amount": 0}, {"amount": -10}, {"amount": 0.001}, {"amount": "NaN"},
            {"amount": "Infinity"}, {"amount": True}, {"amount": 1001},
            {"odds": 99999}, {"bet_type": "unknown"}, {"team_bet_on": "fake"},
            {"matchup": "fake"}, {"game_number": 0}, {"game_number": 8},
            {"request_id": "not-a-uuid"}, {"user_id": 999999},
            {"bet_type": "over_under_points", "team_bet_on": "NotOver"},
            {"bet_type": "spread", "target_value": 9999},
        ]
        for overrides in variants:
            with self.subTest(input=overrides):
                result = self.client.post("/api/place-bet", json=self.bet(line, **overrides))
                self.assertIn(result.status_code, (400, 403, 404, 409, 422), result.text)
                self.assertEqual(self.me()["balance"], 1000)
                self.assertEqual(self.history(), [])

    def test_moneyline_payout_saved_stats_and_no_late_bet(self):
        self.register()
        line = self.lines()[0]
        response = self.client.post("/api/place-bet", json=self.bet(line))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.me()["balance"], 990)
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            response = self.play(line)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertAlmostEqual(self.me()["balance"], round(990 + 10 * line["odds"]["moneyline"][line["team1"]], 2))
        self.assertEqual(self.history()[0]["status"], "won")
        with SessionLocal() as db:
            game = db.query(GameHistory).one()
            self.assertEqual((game.team1_rebounds, game.team2_rebounds), (45, 40))
        self.assertEqual(self.client.post("/api/place-bet", json=self.bet(line)).status_code, 409)
        self.assertEqual(self.play(line).status_code, 409)

    def test_fractional_cent_payout_rounds_half_up_and_stale_quote_conflicts(self):
        self.register()
        line = self.lines()[0]
        quote = dict(line["odds"])
        quote["moneyline"] = {line["team1"]: 1.5, line["team2"]: 2.5}
        with patch.object(api.engine_nba, "calculate_advanced_odds", return_value=quote):
            stale = self.client.post("/api/place-bet", json=self.bet(line, amount=0.01, odds=1.6))
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(self.me()["balance"], 1000)
            response = self.client.post("/api/place-bet", json=self.bet(line, amount=0.01, odds=1.5))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["potential_win"], 0.02)
            with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
                self.assertEqual(self.play(line).status_code, 200)
        with SessionLocal() as db:
            self.assertEqual(db.query(User).one().balance_cents, 100001)
            self.assertEqual(db.query(Bet).one().potential_win_cents, 2)
        self.assertEqual(self.me()["balance"], 1000.01)

    def test_moneyline_loss_and_over_under_push_or_win(self):
        self.register()
        line = self.lines()[0]
        total = line["odds"]["over_under_points"]["line"]
        self.assertEqual(self.client.post("/api/place-bet", json=self.bet(line, team_bet_on=line["team2"])).status_code, 200)
        self.assertEqual(self.client.post("/api/place-bet", json=self.bet(line, "over_under_points")).status_code, 200)
        # Deterministic scores hit the quoted total exactly when it is integral.
        points = int(total)
        result = {"winner": line["team1"], "t1_pts": points - 80, "t2_pts": 80,
                  "t1_rebounds": 45, "t2_rebounds": 40, "total_points": points}
        with patch.object(api.engine_nba, "generate_game_stats", return_value=result):
            self.assertEqual(self.play(line).status_code, 200)
        statuses = {b["bet_type"]: b["status"] for b in self.history()}
        self.assertEqual(statuses["moneyline"], "lost")
        self.assertEqual(statuses["over_under_points"], "push" if points == total else "lost")
        self.assertEqual(self.me()["balance"], 990 if points == total else 980)

    def test_spread_settlement(self):
        self.register()
        line = self.lines()[0]
        self.assertEqual(self.client.post("/api/place-bet", json=self.bet(line, "spread")).status_code, 200)
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            self.assertEqual(self.play(line).status_code, 200)
        margin = 15 + line["odds"]["spread"]["team1_spread"]
        expected = "won" if margin > 0 else "push" if margin == 0 else "lost"
        self.assertEqual(self.history()[0]["status"], expected)
        balance = 990 + (19 if expected == "won" else 10 if expected == "push" else 0)
        self.assertEqual(self.me()["balance"], balance)

    def test_total_win_and_spread_total_push_return_original_stakes(self):
        self.register()
        line = self.lines()[0]
        quote = dict(line["odds"])
        quote["spread"] = {"team1_spread": -2, "team2_spread": 2, "odds": 1.9}
        quote["over_under_points"] = {"line": 210, "over_odds": 1.9, "under_odds": 1.9}
        with patch.object(api.engine_nba, "calculate_advanced_odds", return_value=quote):
            line = self.lines()[0]
            for kind in ("spread", "over_under_points"):
                response = self.client.post("/api/place-bet", json=self.bet(line, kind))
                self.assertEqual(response.status_code, 200, response.text)
            result = {"winner": line["team1"], "t1_pts": 106, "t2_pts": 104,
                      "t1_rebounds": 45, "t2_rebounds": 40, "total_points": 210}
            with patch.object(api.engine_nba, "generate_game_stats", return_value=result):
                self.assertEqual(self.play(line).status_code, 200)
            self.assertEqual(self.me()["balance"], 1000)
            self.assertEqual([bet["status"] for bet in self.history()], ["push", "push"])
            next_line = self.lines()[0]
            self.assertEqual(self.client.post("/api/place-bet", json=self.bet(next_line, "over_under_points")).status_code, 200)
            with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
                self.assertEqual(self.play(next_line).status_code, 200)
            self.assertEqual(self.history()[0]["status"], "won")
            self.assertEqual(self.me()["balance"], 1009)

    def test_series_finishes_and_series_bet_pays_once(self):
        self.register()
        line = self.lines()[0]
        self.assertEqual(self.client.post("/api/place-bet", json=self.bet(line, "series_winner")).status_code, 200)
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            response = self.client.post("/api/simulate-series-auto", json={"matchup": line["series_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        with SessionLocal() as db:
            games = db.query(GameHistory).all()
            self.assertEqual(len(games), 4)
            self.assertEqual([g.game_number for g in games], [1, 2, 3, 4])
        expected = round(990 + 10 * line["odds"]["series_winner"][line["team1"]], 2)
        self.assertEqual(self.me()["balance"], expected)
        self.assertEqual(self.history()[0]["status"], "won")
        self.client.post("/api/simulate-series-auto", json={"matchup": line["series_id"]})
        self.assertEqual(self.me()["balance"], expected)

    def test_futures_tournament_completion_and_closed_market(self):
        self.register()
        line = self.lines()[0]
        futures = self.client.get("/api/futures-lines").json()["futures_lines"]
        quote = next(item for item in futures if item["team"] == line["team1"])
        body = self.bet(line, "futures_champion", matchup="NBA Finals", game_number=0,
                        team_bet_on=quote["team"], odds=quote["odds"])
        response = self.client.post("/api/place-bet", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            response = self.client.post("/api/simulate-tournament-auto")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.lines(), [])
        self.assertEqual(self.history()[0]["status"], "won")
        self.assertEqual(self.me()["balance"], round(990 + 10 * quote["odds"], 2))
        body["request_id"] = str(uuid4())
        self.assertEqual(self.client.post("/api/place-bet", json=body).status_code, 409)

    def test_eliminated_futures_and_future_round_simulation_are_rejected(self):
        self.register()
        line = self.lines()[0]
        futures = self.client.get("/api/futures-lines").json()["futures_lines"]
        eliminated_quote = next(item for item in futures if item["team"] == line["team2"])
        response = self.client.post("/api/simulate-game", json={"matchup": "NBA Finals", "game_number": 1})
        self.assertIn(response.status_code, (404, 409))
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            response = self.client.post("/api/simulate-series-auto", json={"matchup": line["series_id"]})
        self.assertEqual(response.status_code, 200, response.text)
        body = self.bet(line, "futures_champion", matchup="NBA Finals", game_number=0,
                        team_bet_on=eliminated_quote["team"], odds=eliminated_quote["odds"])
        self.assertEqual(self.client.post("/api/place-bet", json=body).status_code, 409)
        self.assertEqual(self.me()["balance"], 1000)

    def test_idempotent_bet_retry_and_changed_payload(self):
        self.register()
        body = self.bet()
        first = self.client.post("/api/place-bet", json=body)
        self.assertEqual(first.status_code, 200, first.text)
        retry = self.client.post("/api/place-bet", json=body)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(self.me()["balance"], 990)
        self.assertEqual(len(self.history()), 1)
        body["amount"] = 20
        self.assertEqual(self.client.post("/api/place-bet", json=body).status_code, 409)
        self.assertEqual(self.me()["balance"], 990)

    def test_concurrent_spending_cannot_exceed_balance(self):
        self.register()
        cookies = dict(self.client.cookies)
        line = self.lines()[0]
        def place(_):
            with TestClient(api.app) as client:
                client.cookies.update(cookies)
                return client.post("/api/place-bet", json=self.bet(line, amount=700)).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(place, range(2)))
        self.assertEqual(statuses.count(200), 1, statuses)
        self.assertEqual(self.me()["balance"], 300)
        self.assertEqual(len(self.history()), 1)

    def test_private_tournaments_and_cross_user_protection(self):
        self.register()
        own_line = self.lines()[0]
        own_id = self.me().get("user_id", self.me().get("id"))
        self.client.post("/api/place-bet", json=self.bet(own_line))
        with TestClient(api.app) as other:
            self.register("other_user", other)
            self.assertEqual(self.history(other), [])
            response = other.get(f"/api/user/{own_id}")
            self.assertIn(response.status_code, (403, 404))
            response = other.post("/api/place-bet", json=self.bet(self.lines(other)[0], user_id=own_id))
            self.assertIn(response.status_code, (403, 422))
            with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
                self.assertEqual(self.play(self.lines(other)[0], other).status_code, 200)
            self.assertEqual(other.post("/api/reset-tournament").status_code, 200)
        self.assertEqual(self.lines()[0]["next_game_number"], 1)
        self.assertEqual(self.me()["balance"], 990)
        self.assertEqual(self.history()[0]["status"], "pending")

    def test_concurrent_same_request_is_charged_once(self):
        self.register()
        cookies = dict(self.client.cookies)
        body = self.bet()
        def place(_):
            with TestClient(api.app) as client:
                client.cookies.update(cookies)
                return client.post("/api/place-bet", json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(place, range(2)))
        self.assertEqual(statuses, [200, 200])
        self.assertEqual(self.me()["balance"], 990)
        self.assertEqual(len(self.history()), 1)

    def test_concurrent_same_game_has_one_result_and_one_payout(self):
        self.register()
        cookies = dict(self.client.cookies)
        line = self.lines()[0]
        self.client.post("/api/place-bet", json=self.bet(line))
        def play(_):
            with TestClient(api.app) as client:
                client.cookies.update(cookies)
                return self.play(line, client).status_code
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(play, range(2)))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.me()["balance"], round(990 + 10 * line["odds"]["moneyline"][line["team1"]], 2))
        with SessionLocal() as db:
            self.assertEqual(db.query(GameHistory).count(), 1)

    def test_bailout_rejects_funded_wallet_and_throttles_retries(self):
        self.register()
        self.assertIn(self.client.post("/api/reload-bank", json={}).status_code, (400, 409))
        with SessionLocal() as db:
            user = db.query(User).one()
            user.balance_cents = 0
            user.last_reload = None
            db.commit()
        response = self.client.post("/api/reload-bank", json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.me()["balance"], 1000)
        with SessionLocal() as db:
            user = db.query(User).one()
            user.balance_cents = 0
            db.commit()
        self.assertEqual(self.client.post("/api/reload-bank", json={}).status_code, 429)
        self.assertEqual(self.me()["balance"], 0)

    def test_simulation_and_reset_action_retries_are_idempotent(self):
        self.register()
        line = self.lines()[0]
        body = {"request_id": str(uuid4()), "matchup": line["series_id"], "game_number": 1}
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            first = self.client.post("/api/simulate-game", json=body)
            retry = self.client.post("/api/simulate-game", json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(first.json(), retry.json())
        with SessionLocal() as db:
            self.assertEqual(db.query(GameHistory).count(), 1)
        reset = {"request_id": str(uuid4())}
        first = self.client.post("/api/reset-tournament", json=reset)
        retry = self.client.post("/api/reset-tournament", json=reset)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(first.json(), retry.json())
        with SessionLocal() as db:
            self.assertEqual(db.query(Tournament).count(), 2)

    def test_bailout_action_retry_is_idempotent(self):
        self.register()
        with SessionLocal() as db:
            user = db.query(User).one()
            user.balance_cents = 0
            user.last_reload = None
            db.commit()
        body = {"request_id": str(uuid4())}
        first = self.client.post("/api/reload-bank", json=body)
        retry = self.client.post("/api/reload-bank", json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(first.json(), retry.json())
        self.assertEqual(self.me()["balance"], 1000)

    def test_cookie_csrf_rejects_untrusted_origin(self):
        self.register()
        result = self.client.post("/api/reset-tournament", headers={"Origin": "https://untrusted.invalid"})
        self.assertEqual(result.status_code, 403)
        result = self.client.post("/api/reset-tournament", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(result.status_code, 200, result.text)

    def test_reset_refunds_pending_and_preserves_settled_game_history(self):
        self.register()
        line = self.lines()[0]
        self.client.post("/api/place-bet", json=self.bet(line))
        with patch.object(api.engine_nba, "generate_game_stats", self.game_result):
            self.assertEqual(self.play(line).status_code, 200)
        settled_balance = self.me()["balance"]
        self.client.post("/api/place-bet", json=self.bet(self.lines()[0]))
        self.assertEqual(self.me()["balance"], settled_balance - 10)
        with SessionLocal() as db:
            old_tournament = db.query(GameHistory).one().tournament_id
        response = self.client.post("/api/reset-tournament")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.me()["balance"], settled_balance)
        self.assertEqual({b["status"] for b in self.history()}, {"won", "cancelled"})
        self.assertEqual(self.lines()[0]["next_game_number"], 1)
        with SessionLocal() as db:
            self.assertEqual(db.query(GameHistory).filter_by(tournament_id=old_tournament).count(), 1)
            self.assertEqual(db.query(Tournament).count(), 2)

    def test_stale_season_cannot_change_new_season_but_old_retry_still_works(self):
        self.register()
        view = self.client.get('/api/betting-lines').json()
        tournament_id, line = view['tournament_id'], view['betting_lines'][0]
        bet = self.bet(line, tournament_id=tournament_id)
        original = self.client.post('/api/place-bet', json=bet)
        self.assertEqual(original.status_code, 200, original.text)
        reset = self.client.post('/api/reset-tournament', json={'tournament_id': tournament_id})
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertNotEqual(reset.json()['tournament_id'], tournament_id)
        self.assertEqual(self.client.post('/api/place-bet', json=bet).json(), original.json())

        stale_bet = self.bet(line, tournament_id=tournament_id)
        stale_series = {'tournament_id': tournament_id, 'matchup': line['series_id'], 'game_number': 1}
        for path, payload in (
            ('place-bet', stale_bet), ('simulate-game', stale_series), ('simulate-series-auto', stale_series),
            ('simulate-tournament-auto', {'tournament_id': tournament_id}),
            ('reset-tournament', {'tournament_id': tournament_id}),
            ('reload-bank', {'tournament_id': tournament_id}),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(f'/api/{path}', json=payload).status_code, 409)
        self.assertEqual(self.me()['balance'], 1000)
        self.assertEqual([bet['status'] for bet in self.history()], ['cancelled'])
        with SessionLocal() as db:
            self.assertEqual(db.query(GameHistory).count(), 0)
            self.assertEqual(db.query(Tournament).count(), 2)

    def test_series_auto_rejects_outdated_game_number(self):
        self.register()
        view = self.client.get('/api/betting-lines').json()
        line = view['betting_lines'][0]
        body = {'tournament_id': view['tournament_id'], 'matchup': line['series_id'], 'game_number': 1}
        with patch.object(api.engine_nba, 'generate_game_stats', self.game_result):
            self.assertEqual(self.client.post('/api/simulate-game', json=body).status_code, 200)
            self.assertEqual(self.client.post('/api/simulate-series-auto', json=body).status_code, 409)
        self.assertEqual(self.lines()[0]['next_game_number'], 2)

    def test_series_failure_rolls_back_games_and_payouts(self):
        self.register()
        line = self.lines()[0]
        self.client.post("/api/place-bet", json=self.bet(line))
        calls = 0
        def failure(team1, team2, series_history=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Injected simulation failure")
            return self.game_result(team1, team2, series_history)
        with patch.object(api.engine_nba, "generate_game_stats", side_effect=failure):
            response = self.client.post("/api/simulate-series-auto", json={"matchup": line["series_id"]})
        self.assertGreaterEqual(response.status_code, 500)
        self.assertEqual(self.me()["balance"], 990)
        self.assertEqual(self.history()[0]["status"], "pending")
        with SessionLocal() as db:
            self.assertEqual(db.query(GameHistory).count(), 0)


if __name__ == "__main__":
    unittest.main()
